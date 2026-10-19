# 📅 Smart Timetable Portal (Institutional Academic Timetable System)

A modern, fast, web-based timetable generator designed specifically for college departments and academic institutions. It provides instant conflict-free schedule generation, faculty availability matrices, lab block allocation, customizable constraint weights, and wall-chart printing.

---

## ✨ Features

- 🚀 **1-Click Auto-Scheduler**: Constraint-satisfaction heuristic solver that eliminates teacher double-booking, room clashes, batch conflicts, and lunch overlaps.
- 👨‍🏫 **Faculty Availability Matrix**: Visually click and mark busy slots for any faculty member.
- 🔬 **Laboratory Block Support**: Handles 2-hour or 3-hour continuous lab blocks with proper room types.
- 📊 **Multi-View Timetable Grid**: Toggle between **Class View**, **Faculty Individual Schedule View**, and **Room Occupancy View**.
- ✍️ **Interactive Slot Adjuster**: Move or swap classes with live clash warning feedback.
- 🖨️ **Print & PDF Ready**: Clean A4 formatted wall-chart layout for department boards.
- 📥 **CSV / Excel Export**: One-click data download.
- ⚡ **Preset Data Included**: Includes a realistic sample Engineering Department scenario ready to test in 1 click.

---

## 🛠️ Local Quickstart

### Prerequisites
- Python 3.9+

### Setup & Run
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python app.py
```

Open your browser and visit: **`http://localhost:5000`**

---

## ☁️ Deployment

### 1. Render (Recommended for full persistence)
1. In [Render.com](https://render.com), click **New Web Service** and connect `PradhanArpan/scheduler`.
2. Render automatically picks up `render.yaml` or `Dockerfile` and deploys it with one click.

### 2. Vercel
1. Import `PradhanArpan/scheduler` in [Vercel](https://vercel.com).
2. The bundled `vercel.json` and `@vercel/python` builder will automatically handle deployment.