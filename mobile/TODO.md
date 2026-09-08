# TechVanta Mobile App (BhoomiScan AI) - TODO & API Enhancement Notes

## API & Backend Observations

The mobile app currently consumes the existing `/api/v1` FastAPI backend endpoints without modifying any backend source files, in strict accordance with policy.

### Future Mobile Enhancements & API Proposals

1. **Offline Capture Queue & Deferred Uploads**
   - *Proposal*: Add an offline SQLite queue in the mobile app so field verifiers in low-connectivity areas can capture land records offline, storing images locally before syncing when connectivity is restored.
   - *Backend Impact*: Support batch status sync or bulk document upload endpoint `POST /api/v1/documents/bulk-upload`.

2. **Push Notifications for Field Verifier Assignments**
   - *Proposal*: Register Expo push notification tokens for field verifiers so they get notified instantly when a document in their assigned district requires manual review.
   - *Backend Impact*: Add `POST /api/v1/users/me/push-token` endpoint and integrate with Expo Push Notification API.

3. **Biometric Authentication (FaceID / TouchID)**
   - *Proposal*: Enable fast local biometric unlock via `expo-local-authentication` after initial JWT auth.

4. **Multi-Page Document Batch Upload**
   - *Observation*: FastAPI backend `/api/v1/documents/upload` currently accepts a single image file (`file: UploadFile = File(...)`).
   - *Client Handling*: Mobile app captures multi-page document photo batches and attaches metadata `(Page X of Y)` to each uploaded document item.

5. **GIS Map Layer Integration for Cadastral Maps**
   - *Proposal*: Mobile GeoJSON tile overlay using Mapbox or React Native Maps to render land parcel boundaries directly on the field verifier's device.

6. **Location Reference Master Endpoint**
   - *Observation*: FastAPI backend does not currently expose a master endpoint for revenue village/tehsil dropdowns (`/api/v1/locations/reference`).
   - *Client Handling*: Mobile app collects `village` and `tehsil` via free-text inputs with `expo-location` GPS reverse-geocoding autofill.
