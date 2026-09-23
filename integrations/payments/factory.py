from integrations.payments.base import PaymentProvider
from integrations.payments.cash_provider import CashBankProvider
from integrations.payments.esewa_provider import EsewaProvider
from integrations.payments.khalti_provider import KhaltiProvider
from integrations.payments.stripe_provider import StripeProvider


def get_payment_provider(provider_name: str) -> PaymentProvider:
    """
    Factory function resolving payment provider adapter by name.
    """
    normalized = provider_name.strip().lower()

    if normalized == "stripe":
        return StripeProvider()
    elif normalized == "esewa":
        return EsewaProvider()
    elif normalized == "khalti":
        return KhaltiProvider()
    elif normalized in ("cash", "bank_transfer", "bank"):
        return CashBankProvider(provider_type=normalized)
    else:
        raise ValueError(f"Unsupported payment provider: '{provider_name}'")
