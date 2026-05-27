JOB SEARCH APP — SETUP & USAGE
================================

1. INSTALL DEPENDENCIES
   Open a terminal in this folder and run:
   pip install -r requirements.txt

2. RUN THE WEB APP
   python app.py
   → Opens automatically at http://localhost:5000
   → Press Ctrl+C to stop

3. RUN THE JOB SEARCH
   python job_search.py
   → Saves results to jobs_results.csv
   → Refresh the Job Listings tab in the app to see new results

4. COMMAND LINE TRACKER (optional, app does everything)
   python tracker.py add      — log an application
   python tracker.py week     — this week's applications
   python tracker.py summary  — counts by status

FILES CREATED AUTOMATICALLY:
  applications.csv  — your application log
  jobs_results.csv  — latest job search results
