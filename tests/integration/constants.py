POLL_FUNCTION = "local-mesh-poll-mailbox"
SEND_FUNCTION = "local-mesh-send-message-chunk"
FETCH_FUNCTION = "local-mesh-fetch-message-chunk"
CHECK_PARAMS_FUNCTION = "local-mesh-check-send-parameters"
LOCK_MANAGER_FUNCTION = "local-mesh-lock-manager"
POLL_LOG_GROUP = f"/aws/lambda/{POLL_FUNCTION}"
SEND_LOG_GROUP = f"/aws/lambda/{SEND_FUNCTION}"
FETCH_LOG_GROUP = f"/aws/lambda/{FETCH_FUNCTION}"
LOCK_LOG_GROUP = f"/aws/lambda/{LOCK_MANAGER_FUNCTION}"
CHECK_PARAMS_LOG_GROUP = f"/aws/lambda/{CHECK_PARAMS_FUNCTION}"


GET_MESSAGES_SFN_ARN = (
    "arn:aws:states:eu-west-2:000000000000:stateMachine:local-mesh-get-messages"
)

SEND_MESSAGE_SFN_ARN = (
    "arn:aws:states:eu-west-2:000000000000:stateMachine:local-mesh-send-message"
)

SANDBOX_URL = "https://localhost:8700"

LOCAL_MAILBOXES = ["X26ABC1", "X26ABC2", "X26ABC3"]

MB = 1024 * 1024
