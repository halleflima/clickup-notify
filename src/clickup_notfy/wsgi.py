from clickup_notfy.app import create_app
from clickup_notfy.scheduler import iniciar_scheduler

app = create_app()
iniciar_scheduler(app.config)
