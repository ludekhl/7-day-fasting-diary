# 7-Day Fasting Diary 🥤📓

A simple, elegant web application built with **Flask** to log and visualize your progress during a 7-day fast.  
You can track **weight**, **energy**, **mood**, **water intake**, **feelings**, and **photos** each day.

---

## ✨ Features

- **Dashboard** with:
  - Weight trend graph (powered by Chart.js)
  - Fasting progress bar
  - Recent entries with photos
- **Entries**:
  - Add, edit, and delete daily logs
  - Upload multiple photos per entry
- **Visual design**:
  - Responsive layout with TailwindCSS
  - Minimal, glassy, card-based UI
- **Authentication** *(optional)*:
  - View-only mode for guests
  - Editing requires login (credentials stored in database)
- **Encouragement section**:
  - Motivational benefits of fasting shown at bottom of dashboard
- **Data storage**:
  - SQLite database for portability
  - Images stored in `static/uploads/`

---

## 📂 Project Structure

```text
7-day-fasting-diary/
├── app.py                # Main Flask application
├── requirements.txt      # Python dependencies
├── fasting_diary.db      # SQLite database (auto-created on first run)
├── static/
│   ├── styles.css        # Custom CSS (auto-created if missing)
│   └── uploads/          # Uploaded photos
└── templates/            # Jinja2 HTML templates
    ├── _base.html        # Layout wrapper (nav, footer, styles)
    ├── dashboard.html    # Main dashboard view
    ├── entries.html      # All entries list
    ├── entry_form.html   # Add/edit entry form
    └── entry_view.html   # Single entry view