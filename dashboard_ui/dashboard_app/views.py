import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import DashboardLoginForm, SignUpForm, StreamForm, UserProfileForm
from .models import CCTVStream, ReportEvent, User
from .stream_processor import derive_detection_state


STREAM_PROCESSORS = {}


def _create_event_for_stream(user, stream, event_type, details=None, duration_seconds=0.0):
    ReportEvent.objects.create(
        user=user,
        timestamp=timezone.now(),
        event_type=event_type,
        duration_seconds=float(duration_seconds or 0.0),
        details=details or {},
    )


def _load_pose_model():
    try:
        from ultralytics import YOLO
    except Exception:
        return None

    model_path = Path(__file__).resolve().parents[2] / "yolov8n-pose.pt"
    if not model_path.exists():
        return None
    return YOLO(str(model_path))


def _run_stream_processor(stream_id, user_id, rtsp_url):
    import cv2

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        CCTVStream.objects.filter(id=stream_id).update(status="offline")
        return

    model = _load_pose_model()
    if model is None:
        CCTVStream.objects.filter(id=stream_id).update(status="error")
        cap.release()
        return

    CCTVStream.objects.filter(id=stream_id).update(status="active")
    consecutive_frames = 0
    last_event = None

    while STREAM_PROCESSORS.get(stream_id):
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.2)
            continue

        try:
            results = model(frame, stream=False, conf=0.4, verbose=False)
            keypoints_list = []
            if results and len(results) > 0 and results[0].keypoints is not None:
                keypoints_list = results[0].keypoints.data.cpu().numpy()

            state, is_shaving, confidence, consecutive_frames = derive_detection_state(
                keypoints_list,
                consecutive_frames=consecutive_frames,
                proximity_threshold=150,
                required_frames=5,
            )

            event_type = None
            details = {"rtsp_url": rtsp_url, "confidence": confidence}
            if state == "SHAVING ACTIVE" and last_event != "SHAVING ACTIVE":
                event_type = "SHAVE_ACTIVE_START"
                last_event = state
            elif state != "SHAVING ACTIVE" and last_event == "SHAVING ACTIVE":
                event_type = "SHAVE_ACTIVE_END"
                last_event = state
            elif state == "CUSTOMER SEATED" and last_event != "CUSTOMER SEATED":
                event_type = "SESSION_START"
                last_event = state
            elif state == "EMPTY" and last_event not in {None, "EMPTY"}:
                event_type = "SESSION_END"
                last_event = state

            if event_type:
                user = User.objects.filter(id=user_id).first()
                if user:
                    _create_event_for_stream(user, None, event_type, details=details)
        except Exception:
            pass

        time.sleep(0.2)

    cap.release()
    CCTVStream.objects.filter(id=stream_id).update(status="inactive")


def _start_stream_processor(stream):
    if stream.id in STREAM_PROCESSORS and STREAM_PROCESSORS[stream.id].is_alive():
        return

    stop_flag = {"running": True}
    STREAM_PROCESSORS[stream.id] = threading.Thread(
        target=_run_stream_processor,
        args=(stream.id, stream.user_id, stream.rtsp_url),
        daemon=True,
    )
    STREAM_PROCESSORS[stream.id].start()


def _stop_stream_processor(stream_id):
    if stream_id in STREAM_PROCESSORS:
        STREAM_PROCESSORS.pop(stream_id, None)


def home_redirect(request):
    return redirect("dashboard_app:dashboard")


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard_app:dashboard")
    else:
        form = SignUpForm()
    return render(request, "dashboard_app/signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = DashboardLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("dashboard_app:dashboard")
    else:
        form = DashboardLoginForm()
    return render(request, "dashboard_app/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("dashboard_app:login")


def generate_report_context(user):
    now = timezone.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_day - timedelta(days=now.weekday())
    start_of_month = start_of_day.replace(day=1)

    events_qs = ReportEvent.objects.filter(user=user).order_by('-timestamp')
    durations = [event.duration_seconds for event in events_qs]
    total_sessions = events_qs.count()
    total_shave_time = sum(durations)
    average_session_length = round(total_shave_time / total_sessions, 1) if total_sessions else 0
    active_time = total_shave_time
    people_shaved = total_sessions
    shaves_completed = total_sessions

    recent_events = []
    for event in events_qs[:7]:
        details = event.details or {}
        detail_text = details.get('detail') or details.get('notes') or ''
        recent_events.append({
            'time': event.timestamp.strftime('%H:%M'),
            'event': event.event_type,
            'detail': detail_text,
        })

    if not recent_events:
        recent_events = [
            {'time': '08:10', 'event': 'Session started', 'detail': 'Customer joined'},
            {'time': '08:35', 'event': 'Shave active', 'detail': 'Barber engaged'},
            {'time': '09:05', 'event': 'Session ended', 'detail': 'Completed'},
        ]

    def build_period_summary(periods, label_func, include_minutes=False):
        values = []
        minutes = []
        labels = []
        for period_start in periods:
            period_end = period_start + period_length
            period_events = [event for event in events_qs if period_start <= event.timestamp < period_end]
            labels.append(label_func(period_start))
            values.append(len(period_events))
            minutes.append(round(sum(event.duration_seconds for event in period_events) / 60, 1))
        return labels, values, minutes

    # daily summary for last 7 days
    daily_periods = [start_of_day - timedelta(days=6 - i) for i in range(7)]
    period_length = timedelta(days=1)
    daily_labels, daily_values, daily_minutes = build_period_summary(
        daily_periods, lambda start: start.strftime('%a'), include_minutes=True
    )

    # weekly summary for last 4 weeks
    weekly_periods = [start_of_week - timedelta(weeks=3 - i) for i in range(4)]
    period_length = timedelta(weeks=1)
    weekly_labels, weekly_values, weekly_minutes = build_period_summary(
        weekly_periods, lambda start: f'W{k+1}' if False else start.strftime('W%U'), include_minutes=True
    )

    # monthly summary for last 6 months
    monthly_periods = []
    for i in range(5, -1, -1):
        month = (start_of_month.month - i - 1) % 12 + 1
        year = start_of_month.year + ((start_of_month.month - i - 1) // 12)
        monthly_periods.append(datetime(year, month, 1, tzinfo=now.tzinfo))
    monthly_labels = [period.strftime('%b') for period in monthly_periods]
    monthly_values = []
    monthly_minutes = []
    for month_start in monthly_periods:
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        month_events = [event for event in events_qs if month_start <= event.timestamp < next_month]
        monthly_values.append(len(month_events))
        monthly_minutes.append(round(sum(event.duration_seconds for event in month_events) / 60, 1))

    duration_bins = [0, 5, 10, 15, 20]
    duration_histogram_values = [0] * (len(duration_bins) + 1)
    for duration in durations:
        minutes = duration / 60
        for idx, threshold in enumerate(duration_bins):
            if minutes <= threshold:
                duration_histogram_values[idx] += 1
                break
        else:
            duration_histogram_values[-1] += 1

    duration_histogram = {
        'labels': ['0-5 min', '5-10 min', '10-15 min', '15-20 min', '>20 min'],
        'values': duration_histogram_values,
    }

    average_daily_minutes = round(sum(daily_minutes) / len(daily_minutes), 1) if daily_minutes else 0
    average_weekly_minutes = round(sum(weekly_minutes) / len(weekly_minutes), 1) if weekly_minutes else 0
    average_monthly_minutes = round(sum(monthly_minutes) / len(monthly_minutes), 1) if monthly_minutes else 0

    return {
        'total_sessions': total_sessions,
        'total_shave_time': total_shave_time,
        'total_shave_time_minutes': round(total_shave_time / 60),
        'average_session_length': average_session_length,
        'average_session_length_minutes': round(average_session_length / 60, 1),
        'active_time': active_time,
        'active_time_minutes': round(active_time / 60),
        'people_shaved': people_shaved,
        'shaves_completed': shaves_completed,
        'average_daily_minutes': average_daily_minutes,
        'average_weekly_minutes': average_weekly_minutes,
        'average_monthly_minutes': average_monthly_minutes,
        'events': recent_events,
        'daily': {
            'labels': daily_labels,
            'values': daily_values,
            'minutes': daily_minutes,
            'labels_json': json.dumps(daily_labels),
            'values_json': json.dumps(daily_values),
            'minutes_json': json.dumps(daily_minutes),
        },
        'weekly': {
            'labels': weekly_labels,
            'values': weekly_values,
            'minutes': weekly_minutes,
            'labels_json': json.dumps(weekly_labels),
            'values_json': json.dumps(weekly_values),
            'minutes_json': json.dumps(weekly_minutes),
        },
        'monthly': {
            'labels': monthly_labels,
            'values': monthly_values,
            'minutes': monthly_minutes,
            'labels_json': json.dumps(monthly_labels),
            'values_json': json.dumps(monthly_values),
            'minutes_json': json.dumps(monthly_minutes),
        },
        'duration_histogram': {
            **duration_histogram,
            'labels_json': json.dumps(duration_histogram['labels']),
            'values_json': json.dumps(duration_histogram['values']),
        },
        'start_of_day': start_of_day,
        'start_of_week': start_of_week,
        'start_of_month': start_of_month,
    }


@login_required
def dashboard(request):
    report_context = generate_report_context(request.user)
    streams = CCTVStream.objects.filter(user=request.user)
    return render(request, "dashboard_app/dashboard.html", {
        "report": report_context,
        "streams": streams,
    })


@login_required
def clear_history(request):
    ReportEvent.objects.filter(user=request.user).delete()
    messages.success(request, "Shave history cleared. New session data can be recorded from your next test run.")
    return redirect("dashboard_app:dashboard")


@login_required
def daily_report(request):
    report_context = generate_report_context(request.user)
    return render(request, "dashboard_app/daily_report.html", {"report": report_context})


@login_required
def weekly_report(request):
    report_context = generate_report_context(request.user)
    return render(request, "dashboard_app/weekly_report.html", {"report": report_context})


@login_required
def monthly_report(request):
    report_context = generate_report_context(request.user)
    return render(request, "dashboard_app/monthly_report.html", {"report": report_context})


@login_required
def profile(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect(reverse("dashboard_app:profile"))
    else:
        form = UserProfileForm(instance=request.user)

    streams = CCTVStream.objects.filter(user=request.user)
    stream_form = StreamForm()

    return render(request, "dashboard_app/profile.html", {
        "form": form,
        "streams": streams,
        "stream_form": stream_form,
    })


@login_required
def add_stream(request):
    if request.method == "POST":
        form = StreamForm(request.POST)
        if form.is_valid():
            stream = form.save(commit=False)
            stream.user = request.user
            stream.save()
            _start_stream_processor(stream)
            messages.success(request, "RTSP stream added and processing started.")
            return redirect(reverse("dashboard_app:profile"))
    return redirect(reverse("dashboard_app:profile"))


@login_required
def remove_stream(request, stream_id):
    stream = CCTVStream.objects.filter(id=stream_id, user=request.user).first()
    if stream:
        _stop_stream_processor(stream.id)
        stream.delete()
        messages.success(request, "Stream removed.")
    return redirect(reverse("dashboard_app:profile"))
