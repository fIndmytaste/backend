from celery import shared_task


@shared_task(name='admin_manager.send_email_campaign')
def send_email_campaign_task(campaign_id):
    from admin_manager.campaigns import send_campaign
    send_campaign(campaign_id)


@shared_task(name='admin_manager.evaluate_rider_rewards')
def evaluate_rider_rewards_task():
    from admin_manager.rewards import evaluate_rider_rewards
    return evaluate_rider_rewards()
