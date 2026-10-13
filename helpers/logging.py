'''Structured logging: JSON lines in production, readable text locally.'''

import json
import logging
from datetime import datetime, timezone

# Attributes every LogRecord has; anything else was passed via `extra=`
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {'message', 'asctime', 'request_id'}


class RequestIdFilter(logging.Filter):
    '''Stamp each record with the current request id (blank outside requests).'''

    def filter(self, record):
        from audit.context import current_request_id

        record.request_id = current_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            'time': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', ''),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)
