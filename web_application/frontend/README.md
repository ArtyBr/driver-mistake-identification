# Frontend UI Architecture

The frontend is a modern Single Page Application (SPA) built with React 19 and Vite. It focuses on providing a responsive, interactive dashboard for reviewing complex driver safety data.

## Detailed File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/             # Generic UI atoms (FileDropZone.jsx).
│   │   │   └── FileDropZone.jsx
│   │   │
│   │   └── features/           # Domain-specific functional blocks.
│   │       ├── Uploader.jsx    # Handles file selection & upload logic.
│   │       ├── VideoPlayer.jsx # The main result visualization dashboard.
│   │       └── video_player/   # Sub-components of the player.
│   │           ├── VideoDisplay.jsx # Wrapper for HTML5 <video> & <canvas>.
│   │           ├── Timeline.jsx     # Interactive event timeline.
│   │           ├── LogViewer.jsx    # Text-based event log.
│   │           └── Legend.jsx       # Visual guide for colors.
│   │
│   ├── hooks/                  # Custom Business Logic (Separation of Concerns).
│   │   ├── useJob.js           # API interactions (Upload, Polling status).
│   │   ├── useVideoPlayback.js # Syncs play/pause/seek between two videos.
│   │   ├── useVideoCanvas.js   # Handles drawing overlays on the canvas.
│   │   └── useVideoAnalysisData.js # Parses/formats raw JSON results.
│   │
│   ├── pages/                  # Top-level Route Views.
│   │   ├── Home.jsx            # Landing page.
│   │   ├── UploadPage.jsx      # Upload interface.
│   │   ├── StatusPage.jsx      # Loading/Progress screen.
│   │   └── ResultPage.jsx      # Final analysis dashboard.
│   │
│   ├── services/
│   │   └── api.js              # Axios instance & typed API calls.
│   │
│   ├── App.jsx                 # Router configuration.
│   └── main.jsx                # React Entry point.
```

## Technology Justification

### 1. Library: React 19
*   **Choice**: We chose React for its Virtual DOM and component-based architecture.
*   **Why?** The `VideoPlayer` component requires complex state management to synchronize the current time, video playback, canvas overlays, and the scrolling event log. React's unidirectional data flow makes reasoning about this state predictable.
*   **Comparison**:
    *   **vs. Vanilla JS**: Manipulating the DOM manually for the timeline and log viewer would result in "spaghetti code" that is hard to maintain.
    *   **vs. Angular**: Angular is a full MVC framework. For this dashboard, which is essentially a few views with one complex player component, Angular's boilerplate (modules, dependency injection) was deemed excessive compared to React's functional components.

### 2. Build Tool: Vite
*   **Choice**: Vite was used for scaffolding and building the project.
*   **Why?** Vite uses native ES Modules during development, resulting in near-instant server start and Hot Module Replacement (HMR). This significantly speeds up the feedback loop when tweaking UI components compared to Webpack-based tools like Create React App (CRA).

### 3. Rendering: HTML5 Canvas
*   **Choice**: Lane lines and gaze vectors are drawn on a transparent `<canvas>` overlaying the video.
*   **Why?**
    *   **Performance**: Drawing lines on a canvas is hardware-accelerated and much faster than rendering thousands of SVG or DOM elements for every frame of video.
    *   **Flexibility**: It allows us to easily clear and redraw the overlay 30 times a second to match the video frame rate without thrashing the DOM.

## Key Components & Design Decisions

### 1. Custom Hooks (Logic Separation)
We avoid "Fat Components" by extracting logic into hooks.
*   **useVideoPlayback**: This is the brain of the player. It manages currentTime, isPlaying, and synchronizes the Road and Face videos so they stay perfectly aligned.
*   **useVideoCanvas**: Uses requestAnimationFrame to draw high-performance overlays (lane lines, gaze vectors) onto a transparent canvas layered on top of the video.

### 2. Dual-Video Synchronization
The application must play two videos simultaneously.
*   **Challenge**: Browsers drift video timing independently.
*   **Solution**: We control one "Master" video (Road) and constantly force the "Slave" video (Face) to match its timestamp within a 15ms threshold inside the animation loop.

### 3. Local-First Data Handling
*   **Uploads**: We use Blob URLs to preview videos immediately after selection, even before upload completes.
*   **Results**: When a job is done, if the user is still in the same session, we use the local file references to save bandwidth. If they reload, we fall back to streaming from the server.

## Build & Deploy

The project uses Vite for lightning-fast HMR (Hot Module Replacement) and optimized production builds.

*   **Dev**: npm run dev (Starts dev server at port 5173).
*   **Build**: npm run build (Outputs minified assets to dist/).
