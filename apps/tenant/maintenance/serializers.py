from decimal import Decimal

from rest_framework import serializers

from apps.tenant.maintenance.models import (
    CleanlinessLevel,
    InspectionType,
    MaintenanceRecord,
    ServiceInterval,
    TelemetryRecord,
    VehicleInspection,
)


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    vehicle_brand = serializers.CharField(source="vehicle.brand", read_only=True)
    vehicle_model = serializers.CharField(source="vehicle.model", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.license_plate", read_only=True)

    class Meta:
        model = MaintenanceRecord
        fields = [
            "id",
            "vehicle",
            "vehicle_brand",
            "vehicle_model",
            "vehicle_plate",
            "service_type",
            "status",
            "scheduled_start",
            "scheduled_end",
            "actual_completion",
            "odometer_reading",
            "cost",
            "service_center",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ScheduleMaintenanceSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField(required=True)
    service_type = serializers.CharField(max_length=100, required=True)
    scheduled_start = serializers.DateTimeField(required=True)
    scheduled_end = serializers.DateTimeField(required=True)
    service_center = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class CompleteMaintenanceSerializer(serializers.Serializer):
    actual_completion = serializers.DateTimeField(required=False)
    odometer_reading = serializers.IntegerField(required=False, min_value=0)
    cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=Decimal("0.00")
    )
    mechanic_notes = serializers.CharField(required=False, allow_blank=True)


class VehicleInspectionSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source="vehicle.license_plate", read_only=True)
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)

    class Meta:
        model = VehicleInspection
        fields = [
            "id",
            "vehicle",
            "vehicle_plate",
            "booking",
            "booking_reference",
            "inspector_id",
            "inspection_type",
            "odometer",
            "fuel_percentage",
            "battery_percentage",
            "exterior_condition",
            "interior_condition",
            "has_new_damage",
            "damage_description",
            "damage_photos",
            "customer_signature",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CreateInspectionSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField(required=True)
    booking_id = serializers.UUIDField(required=False, allow_null=True)
    inspection_type = serializers.ChoiceField(
        choices=InspectionType.choices, default=InspectionType.CHECK_OUT
    )
    odometer = serializers.IntegerField(required=True, min_value=0)
    fuel_percentage = serializers.IntegerField(required=True, min_value=0, max_value=100)
    battery_percentage = serializers.IntegerField(
        required=False, min_value=0, max_value=100, allow_null=True
    )
    exterior_condition = serializers.ChoiceField(
        choices=CleanlinessLevel.choices, default=CleanlinessLevel.GOOD
    )
    interior_condition = serializers.ChoiceField(
        choices=CleanlinessLevel.choices, default=CleanlinessLevel.GOOD
    )
    has_new_damage = serializers.BooleanField(default=False)
    damage_description = serializers.CharField(required=False, allow_blank=True)
    damage_photos = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    customer_signature = serializers.CharField(required=False, allow_blank=True)


class TelemetryRecordSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source="vehicle.license_plate", read_only=True)

    class Meta:
        model = TelemetryRecord
        fields = [
            "id",
            "vehicle",
            "vehicle_plate",
            "odometer",
            "fuel_level",
            "source",
            "latitude",
            "longitude",
            "speed_kph",
            "recorded_at",
        ]
        read_only_fields = fields


class ServiceIntervalSerializer(serializers.ModelSerializer):
    due_status = serializers.SerializerMethodField()

    class Meta:
        model = ServiceInterval
        fields = [
            "id",
            "vehicle",
            "service_name",
            "interval_mileage",
            "interval_days",
            "last_service_mileage",
            "last_service_date",
            "is_active",
            "due_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_due_status(self, obj) -> str:
        return obj.due_status(current_mileage=obj.vehicle.mileage)
