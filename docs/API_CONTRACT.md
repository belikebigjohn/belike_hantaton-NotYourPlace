# API contract v1

Report creation retries: optional `Idempotency-Key` UUID header on POST /reports maps to one report within the current owner session. Establish the cookie with GET /health before the first create. The key is stored in the local draft, is not a report JSON field, and is retained until the response with report ID is saved. Existing report fields can be patched after a replay. Deleting the report removes its key mapping.

All endpoints /api, JSON except multipart analyze/photos and export. Same-origin session in HttpOnly cookie (frontend fetch credentials include). Errors: {error:{code:string,message:string}}. Dates ISO 8601. Confidence: number 0..1 or null, model score not calibrated probability. Boxes [x,y,width,height] in original image pixels or null.

Both-photo OCR: analyze additionally returns `plates_by_photo:{scene:PlateResult,plate:PlateResult}` and `plate_comparison:{status:'match'|'mismatch'|'needs_review',scene_value,plate_value}`. Each PlateResult/candidate includes the correct photo_id; its bounding box only belongs on that original image. The legacy top-level plate prefers the close-up, falls back to the scene if necessary and keeps candidates from both sources.

Human review is separate: `analysis.plate_review:{scene_value:string,plate_value:string,confirmed:boolean}`. Raw OCR values remain in plates_by_photo. For a new analysis, package preparation/export requires a confirmed review with both normalized values equal to the final report.plate. An unreadable or different number requires correction or a replacement image. Machine comparison does not replace this confirmation, even with a high model score.

- GET /health -> {status:'ok',models:object}
- POST /analyze multipart scene_photo, plate_photo -> {plate:{value:string,confidence:number|null,bbox:number[]|null,needs_review:boolean,candidates:array},signs:[{class_code:string,confidence:number,bbox:number[],photo_id:string}],parking_accessibility_evidence:'detected'|'not_detected'|'unknown', explanations:string[], model_versions:object}
- POST /geocode/reverse JSON {latitude,longitude} -> {address:string|null,source:string,needs_manual:boolean}
- POST /reports JSON -> report; GET /reports -> report[]; GET /reports/{id} -> report; PATCH /reports/{id} JSON partial -> report; DELETE /reports/{id} -> {ok:true}
- POST /reports/{id}/photos multipart scene_photo and/or plate_photo -> report
- GET /reports/{id}/photos/{kind} -> original image, kind scene|plate
- GET /reports/{id}/export -> ZIP with originals, statement.txt/html/docx, manifest.json and instruction

Report: {id:string,status:'draft'|'prepared'|'exported'|'sent',created_at:string,updated_at:string,plate:string,address:string,observed_at:string,latitude:number|null,longitude:number|null,accuracy:number|null,location_source:string,designation:string,observation:string,applicant_name:string,applicant_address:string,applicant_email:string,recipient:string,statement:string,confirmed:boolean,photos:object,analysis:object|null}. Fields default empty; status sent only by explicit user action. Store arbitrary report editable fields from this list. Cross-session access returns 404. Frontend keeps selected photo Blobs in IndexedDB until backend acknowledges persistence. No fake demo recognition.


Geocode privacy: body {latitude,longitude,consent?:boolean,provider?:"photon"}. External calls require consent=true, supplied only after explicit in-app choice naming Photon/komoot. Otherwise returns manual fallback without network. Photo provenance Form fields: scene_source/plate_source (camera|upload), scene_captured_at/plate_captured_at optional ISO; upload must not claim a capture time. Analysis may additionally return quality:{scene,plate}, each with warnings array.
