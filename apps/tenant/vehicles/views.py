from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny

from common.permissions.tenant import IsTenantStaffOrAbove
from common.responses.standard import StandardResponseMixin

from apps.tenant.branches.models import Branch
from .models import Category, Transmission, Vehicle, VehicleStatus
from .serializers import (
    CategorySerializer,
    TransmissionSerializer,
    VehicleDetailSerializer,
    VehicleSerializer,
)
from .services import compress_and_save_vehicle_image


class VehicleViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Fleet management & public catalog.
    Public requests only see available/reserved vehicles; staff see all.
    """

    queryset = Vehicle.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "transmission", "fuel_type", "branch", "status"]
    search_fields = ["brand", "model", "license_plate"]
    ordering_fields = ["daily_rate", "year", "created_at"]
    ordering = ["brand", "model"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VehicleDetailSerializer
        return VehicleSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "upload_image", "host_register"]:
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        membership = getattr(self.request, "tenant_membership", None)
        if user and user.is_authenticated and membership and membership.is_active:
            return Vehicle.objects.all()
        # Anonymous public catalog only sees non-decommissioned vehicles
        return Vehicle.objects.exclude(status=VehicleStatus.INACTIVE)

    def perform_create(self, serializer):
        vehicle = serializer.save()
        user_email = getattr(self.request.user, "email", "staff@concierge.local")
        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=user_email,
            action="CREATE_VEHICLE",
            resource_type="Vehicle",
            resource_id=str(vehicle.id),
            details={"brand": vehicle.brand, "model": vehicle.model, "plate": vehicle.license_plate},
        )

    def perform_update(self, serializer):
        vehicle = serializer.save()
        user_email = getattr(self.request.user, "email", "staff@concierge.local")
        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=user_email,
            action="UPDATE_VEHICLE",
            resource_type="Vehicle",
            resource_id=str(vehicle.id),
            details={"status": vehicle.status, "plate": vehicle.license_plate},
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="upload-image",
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[AllowAny],
    )
    def upload_image(self, request):
        """
        Compresses and saves an uploaded vehicle photo, returning metadata with compression ratio.
        Used for uploading photos during new vehicle registration.
        """
        image_file = (
            request.FILES.get("image")
            or request.FILES.get("file")
            or request.FILES.get("photo")
        )
        if not image_file:
            raise ValidationError({"image": "Please provide an image file to upload."})

        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", "general") if tenant else "general"

        caption = request.data.get("caption", "")
        is_primary = str(request.data.get("is_primary", "false")).lower() in ("true", "1")

        result = compress_and_save_vehicle_image(
            uploaded_file=image_file,
            tenant_schema=schema_name,
        )
        result["caption"] = caption
        result["is_primary"] = is_primary

        return self.success_response(
            data=result,
            message="Vehicle image uploaded and compressed successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="host-register",
        permission_classes=[AllowAny],
    )
    def host_register(self, request):
        """
        Public endpoint for vehicle owners to register their vehicle on the Sajilo marketplace.
        Accepts Owner, Vehicle, and Driver details from the 3-step wizard.
        """
        import uuid
        data = request.data
        owner_name = data.get("owner_name", "").strip()
        owner_email = data.get("owner_email", "").strip()
        owner_phone = data.get("owner_phone", "").strip()
        location = data.get("location", "Kathmandu").strip()
        owner_address = data.get("owner_address", "").strip()

        reg_number = data.get("registration_number", "").strip()
        manufacturer = data.get("manufacturer", "").strip()
        model = data.get("model", "").strip()
        try:
            year = int(data.get("manufacture_year", 2023) or 2023)
        except (ValueError, TypeError):
            year = 2023

        vehicle_type = data.get("vehicle_type", "sedan").strip().lower()
        color = data.get("color", "White").strip()
        fuel_type = data.get("fuel_type", "petrol").strip().lower()
        if fuel_type not in ["petrol", "diesel", "hybrid", "electric"]:
            fuel_type = "petrol"

        driver_name = data.get("driver_name", "").strip() or owner_name
        driver_phone = data.get("driver_phone", "").strip() or owner_phone
        driver_license = data.get("license_number", "").strip()
        driver_address = data.get("driver_address", "").strip()
        driver_smoking = str(data.get("driver_smoking", "0")).lower() in ("1", "true", "yes")

        features = data.get("features", [])
        if isinstance(features, str):
            features = [f.strip() for f in features.split(",") if f.strip()]

        images = data.get("images", [])

        branch = Branch.objects.first()
        if not branch:
            branch = Branch.objects.create(
                name="Kathmandu Central Branch",
                code="KTM-01",
                address="Putalisadak, Kathmandu",
                city="Kathmandu",
                phone="+977 974 181 6117",
                email="contact@sajilorental.com",
            )

        rate_map = {
            "sedan": (4500, 2000, 3200),
            "suv": (7500, 3500, 5500),
            "scorpio": (8500, 4000, 6500),
            "van": (9000, 4500, 7000),
            "hiace": (9500, 4800, 7500),
            "ev hiace": (10000, 5000, 8000),
            "compact": (4000, 1800, 2800),
            "pickup": (7000, 3200, 5000),
            "luxury": (15000, 7000, 11000),
        }
        matched_rates = rate_map.get(vehicle_type, (5000, 2500, 3800))
        daily_rate, rate_4h, rate_8h = matched_rates

        ref_id = f"HOST-{uuid.uuid4().hex[:6].upper()}"

        description = (
            f"Host Vehicle Registration ({ref_id})\n"
            f"Owner: {owner_name} ({owner_phone}, {owner_email})\n"
            f"Location: {location}, {owner_address}\n"
            f"Driver: {driver_name} (Phone: {driver_phone}, License: {driver_license})\n"
            f"Smoking Allowed: {'Yes' if driver_smoking else 'No'}"
        )

        license_plate = reg_number if reg_number else f"BA-{uuid.uuid4().hex[:4].upper()}"
        vehicle, _ = Vehicle.objects.update_or_create(
            license_plate=license_plate,
            defaults={
                "branch": branch,
                "brand": manufacturer or "Custom",
                "model": model or "Vehicle",
                "year": year,
                "category": vehicle_type,
                "transmission": "manual" if "manual" in vehicle_type else "automatic",
                "fuel_type": fuel_type,
                "color": color,
                "seats": 5 if "sedan" in vehicle_type or "compact" in vehicle_type else (7 if "scorpio" in vehicle_type or "suv" in vehicle_type else 14),
                "doors": 4,
                "daily_rate": daily_rate,
                "rate_4h": rate_4h,
                "rate_8h": rate_8h,
                "fuel_rate_per_km": 2.50,
                "status": VehicleStatus.AVAILABLE,
                "is_verified": False,
                "driver_included": True,
                "driver_name": driver_name,
                "driver_experience": "Verified Chauffeur",
                "features": features,
                "images": images,
                "description": description,
            }
        )

        return self.success_response(
            data={
                "reference_id": ref_id,
                "vehicle_id": str(vehicle.id),
                "owner_name": owner_name,
                "vehicle_title": f"{vehicle.brand} {vehicle.model} ({vehicle.year})",
                "status": "pending_inspection",
                "message": "Thank you! Your vehicle registration application has been submitted to Sajilo Rental.",
            },
            status_code=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="upload-image",
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[IsTenantStaffOrAbove],
    )
    def upload_vehicle_image(self, request, pk=None):
        """
        Compresses, saves, and attaches a photo directly to an existing vehicle asset.
        """
        vehicle = self.get_object()
        image_file = (
            request.FILES.get("image")
            or request.FILES.get("file")
            or request.FILES.get("photo")
        )
        if not image_file:
            raise ValidationError({"image": "Please provide an image file to upload."})

        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", "general") if tenant else "general"

        caption = request.data.get("caption", f"{vehicle.brand} {vehicle.model}")
        is_primary = str(request.data.get("is_primary", "false")).lower() in ("true", "1")

        result = compress_and_save_vehicle_image(
            uploaded_file=image_file,
            tenant_schema=schema_name,
        )

        current_images = list(vehicle.images or [])
        if is_primary:
            for img in current_images:
                if isinstance(img, dict):
                    img["is_primary"] = False
        elif not current_images:
            is_primary = True

        new_image_entry = {
            "url": result["url"],
            "caption": caption,
            "is_primary": is_primary,
            "original_name": result["original_name"],
            "compressed_size": result["compressed_size"],
            "reduction_percentage": result["reduction_percentage"],
        }
        current_images.append(new_image_entry)
        vehicle.images = current_images
        vehicle.save(update_fields=["images", "updated_at"])

        user_email = getattr(request.user, "email", "staff@concierge.local")
        from apps.tenant.audit.services import AuditService
        AuditService.log(
            actor_email=user_email,
            action="UPLOAD_VEHICLE_IMAGE",
            resource_type="Vehicle",
            resource_id=str(vehicle.id),
            details={
                "url": result["url"],
                "reduction": f"{result['reduction_percentage']}%",
                "compressed_size": result["compressed_size"],
            },
        )

        return self.success_response(
            data={
                "uploaded": result,
                "images": vehicle.images,
            },
            message=f"Image compressed ({result['reduction_percentage']}% saved) and added to {vehicle.display_name}.",
            status_code=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="remove-image",
        permission_classes=[IsTenantStaffOrAbove],
    )
    def remove_image(self, request, pk=None):
        """
        Removes an image URL from the vehicle catalog entry.
        """
        vehicle = self.get_object()
        image_url = request.data.get("url")
        if not image_url:
            raise ValidationError({"url": "Image URL is required to remove."})

        current_images = [
            img for img in (vehicle.images or [])
            if (isinstance(img, dict) and img.get("url") != image_url)
            or (isinstance(img, str) and img != image_url)
        ]

        # Ensure at least one image remains primary if any exist
        if current_images and not any(isinstance(i, dict) and i.get("is_primary") for i in current_images):
            if isinstance(current_images[0], dict):
                current_images[0]["is_primary"] = True

        vehicle.images = current_images
        vehicle.save(update_fields=["images", "updated_at"])

        return self.success_response(
            data={"images": vehicle.images},
            message="Image removed from vehicle.",
        )


class CategoryViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        qs = Category.objects.all()
        if not qs.exists():
            default_categories = [
                ("sports", "Exotic Sports", "High-performance sports cars and supercars"),
                ("luxury", "Luxury Flagship", "Prestigious luxury sedans and executive vehicles"),
                ("suv", "Premium SUV", "Spacious luxury SUVs and all-terrain haulers"),
                ("sedan", "Executive Sedan", "Comfortable business class sedans"),
                ("electric", "Electric / EV", "High-efficiency electric and performance EVs"),
                ("convertible", "Convertible", "Open-top grand tourers and roadsters"),
                ("van", "Van / Minivan", "Multi-passenger luxury coaches and vans"),
                ("economy", "Economy", "Practical and fuel-efficient daily runabouts"),
            ]
            for slug, name, desc in default_categories:
                Category.objects.get_or_create(slug=slug, defaults={"name": name, "description": desc})
            qs = Category.objects.all()
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        if not data.get("slug"):
            from django.utils.text import slugify
            data["slug"] = slugify(data.get("name", "category"))
        serializer.save()

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]


class TransmissionViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    serializer_class = TransmissionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        qs = Transmission.objects.all()
        if not qs.exists():
            default_transmissions = [
                ("automatic", "Automatic", "Seamless automatic transmission"),
                ("manual", "Manual", "Traditional manual stick-shift gearbox"),
                ("dual-clutch", "Dual-Clutch / PDK", "High-performance dual-clutch transmission"),
                ("electric", "Single-Speed EV", "Direct-drive electric motor transmission"),
            ]
            for slug, name, desc in default_transmissions:
                Transmission.objects.get_or_create(slug=slug, defaults={"name": name, "description": desc})
            qs = Transmission.objects.all()
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        if not data.get("slug"):
            from django.utils.text import slugify
            data["slug"] = slugify(data.get("name", "transmission"))
        serializer.save()

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsTenantStaffOrAbove()]
