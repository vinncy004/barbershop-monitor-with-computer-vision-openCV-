# Django Dashboard UI/UX Prompt

Build a Django-based dashboard application that provides daily, weekly, and monthly reporting for barbershop activity and CCTV stream monitoring.

## Requirements

1. Create a separate Django project and app inside this folder.
2. Implement a polished UI/UX dashboard using Django templates, HTML, CSS, and JavaScript.
3. Dashboard features:
   - Daily report view
   - Weekly report view
   - Monthly report view
   - Summary cards for total sessions, total shave time, average session length, and active time
   - Charts or graphs for trends over time
4. Account creation and authentication:
   - User signup with email, phone number, and password
   - Login/logout flow
   - Profile form fields: email, phone, and CCTV RTSP URL(s)
5. CCTV stream setup:
   - Allow users to enter one or more RTSP URLs in their profile or settings
   - Display stream connection status and placeholders for live feed processing
   - Design the UI so the streams can be visually monitored from the dashboard
6. Reporting design:
   - Daily reports should show current day metrics and recent events
   - Weekly reports should show aggregated metrics by day and weekly totals
   - Monthly reports should show aggregated metrics by week/month and overall trends
7. UX best practices:
   - Responsive layout for desktop and tablet
   - Clear navigation between report views
   - Accessible form fields and buttons
   - Use cards, tables, charts, and visual indicators for high-level metrics
8. Backend view logic:
   - Use Django views (class-based or function-based) to render templates
   - Query or mock report data for daily, weekly, monthly views
   - Store user details and RTSP URLs in Django models
   - Provide clean, structured context data for templates

## Deliverables

- Django project folder with app and settings
- Templates for dashboard pages and account creation
- Static CSS and JS files for styling and interaction
- Model definitions for users and CCTV stream configuration
- Views for dashboard reports and user profile management
- A prompt document with the exact task description and requirements

## Notes

Focus on a strong UI/UX experience with a modern dashboard feel. The app should support account creation and RTSP stream configuration, while the report pages clearly separate daily, weekly, and monthly insights.
