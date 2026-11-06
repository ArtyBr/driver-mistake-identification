# Frontend UI

React single-page application for uploading videos, monitoring analysis progress, and reviewing results with synchronised dual-video playback and canvas overlays.

## Usage

```bash
npm install        # Install dependencies
npm run dev        # Dev server on port 5173 (HMR)
npm run build      # Production bundle to dist/
npm run preview    # Serve production bundle locally
npm run lint       # Run ESLint
```

## Files

```
frontend/src/
  components/
    common/
      FileDropZone.jsx         Drag-and-drop file input
    features/
      Uploader.jsx             File selection and upload logic
      VideoPlayer.jsx          Main result visualisation dashboard
      AudioWaveform.jsx        Audio waveform display for sync
      SyncConfirmStep.jsx      Video synchronisation confirmation UI
      video_player/
        VideoDisplay.jsx       HTML5 <video> + <canvas> overlay wrapper
        Timeline.jsx           Interactive event timeline (red=unsafe, green=safe)
        LogViewer.jsx          Text-based event log
        Legend.jsx             Colour guide for event types
  hooks/
    useJob.js                  Upload + polling logic (setInterval, stops on complete/fail)
    useVideoPlayback.js        Synchronises play/pause/seek between road and face videos
    useVideoCanvas.js          requestAnimationFrame canvas overlays (lane lines, gaze vectors)
    useVideoAnalysisData.js    Fetches and caches results.json
    useVideoRecorder.js        Webcam recording for new uploads
    useAuth.jsx                JWT auth state (login/signup/logout)
  pages/
    Home.jsx                   Landing page
    UploadPage.jsx             Upload interface
    StatusPage.jsx             Progress/loading screen
    ResultPage.jsx             Analysis dashboard with dual-video player
    LoginPage.jsx              Login form
    SignupPage.jsx             Registration form
  services/
    api.js                     Axios instance and typed API calls
  App.jsx                      Router configuration
  main.jsx                     React entry point
```

## Dependencies

See `package.json`. Key packages: React 19, Vite, Bootstrap 5, React Router 7, Axios.
