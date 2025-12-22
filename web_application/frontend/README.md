# Frontend UI

The frontend is a **React 19** application initialized with **Vite**. It provides a user-friendly interface for the Driver Mistake Identification system.

## Project Structure

*   `src/components/`: Reusable UI components (e.g., `Uploader.jsx`).
*   `src/services/`: API integration modules (e.g., `api.js`).
*   `src/App.jsx`: Main layout and routing logic.

## Key Technologies

*   **Vite**: Fast build tool and development server.
*   **Axios**: HTTP client for API requests.
*   **Bootstrap 5**: CSS framework for styling.

## Configuration

Environment variables are stored in `.env`:
*   `VITE_API_BASE`: Base URL for the backend API (default: `http://localhost:8000`).

## Commands

### Install Dependencies
```bash
npm install
```

### Run Development Server
```bash
npm run dev
```

### Build for Production
```bash
npm run build
```
The output will be in the `dist/` folder, ready to be served by any static file server.