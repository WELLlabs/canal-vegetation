# Canal Watch — AI Canal Blockage Detection (Frontend)

React + TypeScript + Vite frontend for an AI-powered canal blockage detection system.
Built for irrigation / flood-control field teams: upload a drone image, get an instant
blockage assessment, and download a field report.

## Stack
- React 19 + TypeScript + Vite
- Tailwind CSS v4 (`@tailwindcss/vite`)
- lucide-react for icons

## Getting started
```bash
npm install
npm run dev
```

## Connecting the real backend
This ships with a mock analyzer so the full flow is demoable with no backend running.
To connect your FastAPI/Flask service:

1. Create a `.env` file in the project root:
   ```
   VITE_API_BASE_URL=https://your-backend.example.com
   ```
2. Implement `POST /api/analyze` on the backend, accepting `multipart/form-data`
   with an `image` field, and returning JSON matching the `AnalysisResult` type
   in `src/types.ts`:

   ```json
   {
     "blockageDetected": true,
     "confidence": 92.4,
     "blockageType": "Vegetation",
     "severity": "High",
     "affectedAreaPercent": 38.5,
     "recommendations": ["..."],
     "analyzedAt": "2026-07-02T09:00:00Z",
     "imageId": "img_8f21ac"
   }
   ```

All API logic lives in `src/api/analyzeImage.ts` — once `VITE_API_BASE_URL` is set,
it automatically calls the real endpoint instead of the mock.

## Project structure
```
src/
  api/analyzeImage.ts        # backend integration point (mock + real fetch)
  components/                # Hero, NavBar, UploadZone, ImagePreviewCard, ...
  components/results/        # results dashboard: gauge, severity meter, cards
  utils/generateReport.ts    # client-side report (.txt) download
  types.ts                   # shared AnalysisResult contract
```

## Design system
- Deep channel blue (`canal-*`) + teal data accent (`teal-*`), white surfaces
- Space Grotesk (display), Inter (body), JetBrains Mono (data/telemetry)
- Signature motif: a scanning sweep + reticle corner-brackets over uploaded imagery,
  echoing aerial/vision-model analysis, plus an ambient topographic contour texture
