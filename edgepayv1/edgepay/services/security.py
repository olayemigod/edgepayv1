# -*- coding: utf-8 -*-
import re

SENSITIVE_KEYS = {
	"api_key", "secret_key", "token", "password", "authorization", 
	"webhook_secret", "client_secret", "bearer_token", "base64_auth",
	"client_id"
}

SENSITIVE_PATTERNS = [
	re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
	re.compile(r"Basic\s+[a-zA-Z0-9_\-\.\+/=]+", re.IGNORECASE)
]

def redact_secrets(data):
	"""
	Recursively redacts sensitive values from dictionaries, lists, and strings.
	"""
	if isinstance(data, dict):
		redacted = {}
		for k, v in data.items():
			k_lower = k.lower()
			if any(sk in k_lower for sk in SENSITIVE_KEYS):
				redacted[k] = "[REDACTED]"
			else:
				redacted[k] = redact_secrets(v)
		return redacted
	elif isinstance(data, list):
		return [redact_secrets(item) for item in data]
	elif isinstance(data, str):
		for pattern in SENSITIVE_PATTERNS:
			data = pattern.sub("[REDACTED]", data)
		return data
	else:
		return data
