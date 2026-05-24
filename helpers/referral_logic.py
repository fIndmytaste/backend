import logging
from decimal import Decimal
from django.db import transaction
from account.models import User
from wallet.models import Wallet, WalletTransaction
from product.promo_models import PromoCode, PromoUsage

logger = logging.getLogger(__name__)

def process_referral_reward(order):
    """
    Check if the order qualifies for a referral reward and grant it to the referrer.
    This should be called when an order is successfully paid or delivered.
    """
    print("Processing referral reward for order:", order.id)
    user = order.user
    if not user or not user.referred_by:
        return
    
    # Check if this is the user's first successful order
    from product.models import Order
    successful_orders_count = Order.objects.filter(
        user=user, 
        payment_status='paid'
    ).exclude(id=order.id).count()
    
    print(f"User {user.email} has {successful_orders_count} successful orders before this one.")
    if successful_orders_count > 0:
        # Not the first order
        return
        
    referrer = user.referred_by
    promo = order.promo_code
    
    # If a specific promo was used, check if it defines a referrer reward
    if promo and promo.referrer_reward_type != 'none':
        grant_reward(referrer, promo, user, order)
    else:
        print("No specific promo code with referrer reward found for this order. Checking for default referral promo...")
        # Check if there's a global/default referral promo active
        default_referral_promo = PromoCode.objects.filter(
            promo_type='referral', 
            is_active=True
        ).exclude(referrer_reward_type='none').first()
        
        print(f"Default referral promo found: {default_referral_promo.code if default_referral_promo else 'None'}")
        if default_referral_promo:
            grant_reward(referrer, default_referral_promo, user, order)

def grant_reward(referrer, promo, referee, order):
    """Grant the reward to the referrer based on the promo configuration."""
    reward_type = promo.referrer_reward_type
    reward_value = promo.referrer_reward_value
    
    print(f"Granting reward to referrer {referrer.email}: type={reward_type}, value={reward_value}")
    if not reward_type or reward_type == 'none':
        return

    try:
        with transaction.atomic():
            if reward_type == 'wallet_credit':
                wallet, _ = Wallet.objects.get_or_create(user=referrer)
                wallet.deposit(reward_value)

                WalletTransaction.objects.create(
                    wallet=wallet,
                    user=referrer,
                    amount=reward_value,
                    transaction_type='deposit',
                    status='completed',
                    description=f"Referral reward for inviting {referee.email} (Order #{order.id})"
                )
                logger.info(f"Granted {reward_value} wallet credit to {referrer.email} for referral.")

              
            elif reward_type in ['fixed_amount', 'percentage', 'free_delivery', 'discounted_delivery']:
                print(f"Creating promo code reward for referrer {referrer.email} with type {reward_type} and value {reward_value}.")
                # Generate a one-time promo code for the referrer
                # We use a unique code to avoid collisions
                import uuid
                short_id = uuid.uuid4().hex[:6].upper()
                new_promo_code = f"REF-{referrer.referral_code[:4]}-{short_id}".upper()
                
                new_promo = PromoCode.objects.create(
                    code=new_promo_code,
                    promo_type=reward_type,
                    value=reward_value,
                    is_active=True,
                    usage_limit_per_user=1,
                    total_usage_limit=1,
                    description=f"Referral reward for inviting {referee.email}"
                )
                new_promo.applicable_customers.add(referrer)
                logger.info(f"Generated promo code {new_promo_code} for {referrer.email} as referral reward.")

    except Exception as e:
        logger.error(f"Error granting referral reward to {referrer.email}: {e}")
