from datetime import datetime
from decimal import Decimal

from apps.tenant.pricing.models import (
    AddonPricingType,
    Coupon,
    DiscountType,
    ExtraAddon,
    SeasonalRate,
)
from apps.tenant.vehicles.models import Vehicle


class PricingCalculatorService:
    """
    Dedicated Pricing Engine service.
    Calculates dynamic quotation breakdowns with tiers, seasonal multipliers,
    weekend surcharges, extras, coupons, and taxes.
    """

    DEFAULT_TAX_RATE = Decimal("0.08")  # 8.0% standard sales tax
    GRACE_HOURS = 2

    @classmethod
    def calculate_duration_days(cls, pickup_datetime: datetime, return_datetime: datetime) -> int:
        """Calculates billable 24-hour periods with grace allowance."""
        total_seconds = (return_datetime - pickup_datetime).total_seconds()
        total_hours = total_seconds / 3600.0
        full_days = int(total_hours // 24)
        remainder_hours = total_hours % 24

        billable_days = full_days
        if remainder_hours > cls.GRACE_HOURS:
            billable_days += 1
        elif remainder_hours > 0 and billable_days == 0:
            billable_days = 1

        return max(1, billable_days)

    @classmethod
    def calculate_quote(
        cls,
        vehicle: Vehicle,
        pickup_datetime: datetime,
        return_datetime: datetime,
        addon_ids: list[str] | None = None,
        coupon_code: str | None = None,
    ) -> dict:
        billable_days = cls.calculate_duration_days(pickup_datetime, return_datetime)
        line_items = []

        # 1. Base Rate Tier Resolution
        if billable_days >= 30 and vehicle.monthly_rate:
            effective_daily_rate = vehicle.monthly_rate
            tier_name = "Monthly Discounted Rate"
        elif billable_days >= 7 and vehicle.weekly_rate:
            effective_daily_rate = vehicle.weekly_rate
            tier_name = "Weekly Discounted Rate"
        else:
            effective_daily_rate = vehicle.daily_rate
            tier_name = "Standard Daily Rate"

        base_rental_subtotal = (effective_daily_rate * billable_days).quantize(Decimal("0.01"))
        line_items.append(
            {
                "description": f"{tier_name} ({billable_days} days @ ${effective_daily_rate}/day)",
                "amount": str(base_rental_subtotal),
            }
        )

        # 2. Seasonal Multipliers
        seasonal_rate = SeasonalRate.objects.filter(
            is_active=True,
            start_date__lte=return_datetime.date(),
            end_date__gte=pickup_datetime.date(),
        ).first()

        seasonal_adjustment = Decimal("0.00")
        if seasonal_rate and seasonal_rate.multiplier != Decimal("1.00"):
            adjusted_base = (base_rental_subtotal * seasonal_rate.multiplier).quantize(
                Decimal("0.01")
            )
            seasonal_adjustment = adjusted_base - base_rental_subtotal
            line_items.append(
                {
                    "description": f"Seasonal Rate Adjustment: {seasonal_rate.name} (x{seasonal_rate.multiplier})",
                    "amount": str(seasonal_adjustment),
                }
            )

        vehicle_subtotal = base_rental_subtotal + seasonal_adjustment

        # 3. Add-on Extras
        addons_subtotal = Decimal("0.00")
        processed_addons = []
        if addon_ids:
            addons = ExtraAddon.objects.filter(id__in=addon_ids, is_active=True)
            for addon in addons:
                if addon.pricing_type == AddonPricingType.PER_DAY:
                    addon_price = (addon.price * billable_days).quantize(Decimal("0.01"))
                    desc = f"{addon.name} (${addon.price}/day x {billable_days} days)"
                else:
                    addon_price = addon.price.quantize(Decimal("0.01"))
                    desc = f"{addon.name} (Flat Fee)"

                addons_subtotal += addon_price
                processed_addons.append(
                    {
                        "id": str(addon.id),
                        "name": addon.name,
                        "price": str(addon_price),
                    }
                )
                line_items.append(
                    {
                        "description": desc,
                        "amount": str(addon_price),
                    }
                )

        # 4. Coupon Discounts
        discount_amount = Decimal("0.00")
        if coupon_code:
            coupon = Coupon.objects.filter(code__iexact=coupon_code.strip(), is_active=True).first()
            if coupon and billable_days >= coupon.min_rental_days:
                if coupon.discount_type == DiscountType.PERCENTAGE:
                    discount_amount = (
                        vehicle_subtotal * (coupon.discount_value / Decimal("100.00"))
                    ).quantize(Decimal("0.01"))
                else:
                    discount_amount = min(coupon.discount_value, vehicle_subtotal).quantize(
                        Decimal("0.01")
                    )

                line_items.append(
                    {
                        "description": f"Promo Code: {coupon.code}",
                        "amount": f"-{discount_amount}",
                    }
                )

        taxable_subtotal = max(
            Decimal("0.00"), vehicle_subtotal + addons_subtotal - discount_amount
        )

        # 5. Taxes
        tax_amount = (taxable_subtotal * cls.DEFAULT_TAX_RATE).quantize(Decimal("0.01"))
        line_items.append(
            {
                "description": f"Sales Tax ({(cls.DEFAULT_TAX_RATE * 100).quantize(Decimal('0.1'))}%)",
                "amount": str(tax_amount),
            }
        )

        total_payable = taxable_subtotal + tax_amount
        deposit_amount = vehicle.deposit_amount.quantize(Decimal("0.01"))

        return {
            "billable_days": billable_days,
            "base_price": str(base_rental_subtotal),
            "discount_amount": str(discount_amount),
            "tax_amount": str(tax_amount),
            "deposit_amount": str(deposit_amount),
            "total_price": str(total_payable),
            "line_items": line_items,
            "addons": processed_addons,
        }
