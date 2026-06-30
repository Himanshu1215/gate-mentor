# Syllabus Feature Implementation Plan

## Summary
Build a full Syllabus experience from the existing Topics page. Each subject shows topic-wise progress, and each concept opens a detail view with syllabus metadata, a prerequisite graph, AI-generated notes, uploaded PDF notes, self notes, PYQ navigation, practice navigation, and revision scheduling.

## Backend Changes
- Extend `/api/concepts` to return overall progress, subject progress, estimated learning/revision time, prerequisites, dependents, mastery, status, lock state, and progress percentage.
- Add `GET /api/concepts/{concept_id}` for detail data including prerequisites, dependents, subject progress, revision status, self note, and uploaded files.
- Add persistent self notes:
  - Table: `concept_notes`
  - `GET /api/concepts/{concept_id}/notes`
  - `PUT /api/concepts/{concept_id}/notes`
- Add uploaded file metadata:
  - Table: `concept_files`
  - Update `POST /api/upload` to save metadata after PDF/text ingestion.
  - `GET /api/concepts/{concept_id}/files`
  - `GET /api/concepts/{concept_id}/files/{file_id}` for opening/downloading uploaded files.
- Add manual revision scheduling:
  - Table: `manual_revision_items`
  - `POST /api/revision/schedule`
  - Merge manual entries into `/api/revision/due`.

## Frontend Changes
- Rename the visible learning area to Syllabus.
- Replace the old Topics grid with:
  - Overall GATE DA progress.
  - Per-subject progress bars.
  - Subject tabs.
  - Topic-grouped concept cards.
  - Concept detail view.
- Concept detail includes:
  - Mastery, accuracy, importance, difficulty, learning time, revision time.
  - Prerequisite/current/dependent topic graph.
  - AI-generated study notes through existing `/api/chat`.
  - PDF/text upload for topic notes.
  - Saved self notes.
  - Practice, PYQ, tutor, and revision actions.
- Update Revision page copy so it explains both automatic quiz-based revision and manual syllabus-based revision.

## Acceptance Criteria
- Syllabus loads all subjects and concepts.
- Overall and subject progress bars render.
- Concepts are grouped topic-wise.
- Clicking a concept opens the detail screen.
- AI notes can be generated for a topic.
- A PDF/text file can be uploaded for a topic and appears in the uploaded files list.
- Self notes can be saved and reloaded.
- Practice and PYQ buttons reuse the existing Quiz and PYQ flows.
- Add to Revision schedules the topic and it appears in Revision upcoming/due lists.
- Backend syntax check passes.
- Frontend production build passes.

## Verification Commands
```powershell
venv\Scripts\python.exe -m py_compile presentation\api.py infrastructure\database.py
cd frontend-react
npm run build
```

## Notes
- AI-generated notes, uploaded files, and self notes are intentionally separate.
- Overall progress is based on average mastery across all concepts, so partial learning counts.
- Existing Quiz, PYQ, Tutor, and Revision screens are reused.
