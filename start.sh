#!/usr/bin/env sh
# Container entrypoint for the Render web service.
# Runs DB migrations, then starts Celery (worker + embedded beat) in the
# background and the ASGI server in the foreground.
#
# Celery beat is what fires the weekly rider payout (see CELERY_BEAT_SCHEDULE
# in settings.py -> Friday 10:00). It runs here, inside the web container,
# because the backend deploys as a single Render service.
#
# NOTE: `--beat` embeds the scheduler in the worker. That is correct for a
# single instance. If you ever scale the web service to more than one instance,
# move Celery to its own Render Background Worker so the schedule only fires
# once (otherwise every instance would run the payout and pay riders twice).
set -e

python manage.py migrate --noinput

# Start the Celery worker with the embedded beat scheduler.
# `|| true`-style resilience: if the broker is briefly unavailable the worker
# will keep retrying; the web server still comes up regardless.
celery -A findmytaste worker --beat --loglevel=info &

# Foreground process — keeps the container alive.
exec daphne -b 0.0.0.0 -p 8000 findmytaste.asgi:application
