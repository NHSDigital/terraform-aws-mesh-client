from shared.application import MESHLambdaApplication


class MeshLockManagerApplication(MESHLambdaApplication):
    """
    Lambda for interacting with locks in the dynamo db table
    """

    def initialise(self):
        self.response = self.event.raw_event
        self.body = self.event.get("body")
        self.lock_name = self.body.get("lock_name") or None
        self.execution_id = self.body.get("execution_id") or None

    def start(self):
        if self.operation == "release":
            if self.execution_id and self.lock_name:
                self._release_lock(
                    self.lock_name,
                    self.execution_id,
                )
            else:
                self.log_object.write_log(
                    "MESHSEND0015",
                    None,
                    {"lock_name": self.lock_name, "owner_id": self.execution_id},
                )
        return

    def process_event(self, event):
        event_detail = event.get("EventDetail", {})
        operation = event.get("Operation")
        self.operation = self.EVENT_TYPE(operation).raw_event
        return self.EVENT_TYPE(event_detail)


app = MeshLockManagerApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
