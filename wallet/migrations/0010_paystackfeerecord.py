import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0009_product_variant_category_name"),
        ("wallet", "0009_alter_wallettransaction_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaystackFeeRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[
                            ("collection", "Collection (money in)"),
                            ("payout", "Payout (money out)"),
                            ("reversal", "Reversal (money returned)"),
                        ],
                        default="collection",
                        help_text="Whether this movement brought money in or took money out.",
                        max_length=16,
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        db_index=True,
                        help_text="Paystack reference for the charge/transfer.",
                        max_length=255,
                    ),
                ),
                (
                    "paystack_id",
                    models.CharField(
                        blank=True,
                        help_text="Paystack's own numeric id for the transaction/transfer.",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        blank=True,
                        help_text="card, bank_transfer, dedicated_nuban, transfer, ...",
                        max_length=64,
                        null=True,
                    ),
                ),
                ("currency", models.CharField(default="NGN", max_length=8)),
                (
                    "gross_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        help_text="Amount that moved, in naira, before Paystack's fee.",
                        max_digits=12,
                    ),
                ),
                (
                    "fee_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        help_text="What Paystack charged on this movement, in naira.",
                        max_digits=12,
                    ),
                ),
                (
                    "net_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        help_text="Settled to us (collection) or total debited (payout).",
                        max_digits=12,
                    ),
                ),
                (
                    "is_estimated",
                    models.BooleanField(
                        default=False,
                        help_text="True when the fee came from our schedule, not from Paystack.",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("webhook", "Paystack webhook"),
                            ("verify", "Paystack verify API"),
                            ("balance_ledger", "Paystack balance ledger"),
                            ("backfill", "Backfilled from stored payload"),
                            ("estimate", "Estimated from fee schedule"),
                        ],
                        default="webhook",
                        help_text="Where this row's numbers came from.",
                        max_length=32,
                    ),
                ),
                (
                    "paid_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        help_text="When Paystack processed the movement.",
                        null=True,
                    ),
                ),
                ("raw_payload", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        help_text="The order paid for, when this is an order collection.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="paystack_fees",
                        to="product.order",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        help_text="The customer who paid, or the recipient who was paid out.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="paystack_fees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "wallet_transaction",
                    models.ForeignKey(
                        blank=True,
                        help_text="The platform transaction this Paystack movement settles.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="paystack_fees",
                        to="wallet.wallettransaction",
                    ),
                ),
            ],
            options={
                "ordering": ["-paid_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="paystackfeerecord",
            index=models.Index(
                fields=["direction", "paid_at"], name="wallet_pays_directi_2a1c3f_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="paystackfeerecord",
            constraint=models.UniqueConstraint(
                fields=("direction", "reference"),
                name="unique_paystack_fee_per_reference",
            ),
        ),
    ]
