# Underground Parking Organizer

An interactive web application designed to automatically plan and optimize underground parking lot layouts. Users can draw custom basement outlines, specify structural column/obstacle blocked zones, set the snap entrance point, and generate space-efficient layouts (supporting parallel margin spots and perpendicular interior spots).

---

## Architecture & Technology Stack

- **Frontend**: React (Vite, vanilla CSS styling, SVG rendering, Lucide icons)
- **Backend**: FastAPI, Shapely, NumPy, Uvicorn (REST API for computational geometry layout calculations)

---

## Prerequisites

Ensure you have the following installed on your machine:
- **Node.js** (v16.0.0 or higher) & **npm**
- **Python** (v3.8 or higher) & **pip**

---

## Installation & Running Instructions

### 1. Run the Backend (Python FastAPI)

1. Open your terminal and navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the local Uvicorn development server:
   ```bash
   uvicorn main:app --reload
   ```
   *The API will be available at: `http://127.0.0.1:8000`*

---

### 2. Run the Frontend (React Vite)

1. Open a new terminal window and navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install the frontend dependencies:
   ```bash
   npm install
   ```
3. Start the Vite local development server:
   ```bash
   npm run dev
   ```
   *The application will open in your browser at: `http://localhost:5173`*

