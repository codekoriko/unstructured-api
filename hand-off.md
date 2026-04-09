# Implementing Kestra Callback Authentication in Supabase Edge Functions

The `unstructured-api` has been updated to accept an optional `callback_headers` parameter as part of its async webhook functionality. This parameter allows the caller to specify HTTP headers (such as `Authorization`) to be included when the `unstructured-api` makes its POST request back to Kestra.

This document provides snippets and context for implementing this in the `ingest-unstructured` edge function to securely authenticate the callback with Kestra.

## Why?

When Kestra pauses the `wait-for-unstructured` task, it waits for a webhook to resume. The Kestra resume endpoint typically requires authentication, specifically `KESTRA_AUTH_BASIC`. By passing the credentials down to `unstructured-api`, we can ensure that the API safely passes them along during the `POST` callback to Kestra without hardcoding them in the API or exposing them purely in the URL structure.

## Key Insights

The `unstructured-api` endpoint expects `callback_headers` to be a JSON string representing a dictionary of headers.

For example:
```json
{"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}
```

### 1. `buildUnstructuredCallbackHeaders` Utility
You should create a utility function that formats the JSON string containing the Basic Auth header required by Kestra:

```typescript
/**
 * Builds the JSON string representing the callback headers to be forwarded
 * by the Unstructured API back to Kestra.
 *
 * @param kestraAuthBasic - The configured Basic Auth string (e.g., "username:password")
 * @returns JSON stringified headers object
 */
export function buildUnstructuredCallbackHeaders(kestraAuthBasic: string): string {
  const credentialsBase64 = btoa(kestraAuthBasic)
  const headers = {
    Authorization: `Basic ${credentialsBase64}`
  }
  return JSON.stringify(headers)
}
```

### 2. Attaching to `FormData`
In `ingest-unstructured/index.ts`, when preparing the payload to send to `unstructured-api`, you must append the `callback_headers` alongside `callback_url`.

```typescript
import { buildUnstructuredCallbackHeaders } from '~~/_shared/kestraResumeUrl.ts'
// ... (imports)

// Inside `unstructuredProcessing` function:

if (executionId) {
  // 1. Build the Kestra resume URL
  const callbackUrl = buildKestraResumeUrl(parsedEnv.kestraApiBaseUrl, executionId)
  form.append('callback_url', callbackUrl)
  
  // 2. Append the callback headers
  form.append(
    'callback_headers', // MUST match what unstructured-api expects
    buildUnstructuredCallbackHeaders(parsedEnv.kestraAuthBasic)
  )
}
```

### 3. Shared Context (Unstructured API updates)
- `callback_headers` is accepted as an optional text parameter by the `unstructured-api`.
- When the `unstructured-api` finishes processing the document and PUTs the result to the destination bucket, it parses the `callback_headers` JSON string and injects those headers directly into the `requests.post()` call to Kestra.
- This ensures Kestra accurately authenticates the request as an authorized webhook resume event.