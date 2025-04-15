from aw_client import ActivityWatchClient
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import argparse
import json
import requests


def get_window_activity(client, start_date, end_date, bucket_id=None):
    """Get window activity data and return as DataFrame"""
    if bucket_id is None:
        buckets = client.get_buckets()
        window_buckets = [bid for bid in buckets.keys() if 'aw-watcher-window' in bid]
        if not window_buckets:
            raise Exception("No window watcher buckets found")
        bucket_id = window_buckets[0]
        print(f"Using window bucket: {bucket_id}")

    events = client.get_events(bucket_id, start=start_date, end=end_date)
    print(f"Found {len(events)} window events")

    app_times = {}
    for event in events:
        # Handle both dictionary and string data formats
        if isinstance(event.data, str):
            try:
                event_data = json.loads(event.data)
            except json.JSONDecodeError:
                event_data = {"app": "Unknown"}
        else:
            event_data = event.data

        app_name = event_data.get('app', 'Unknown')
        duration_seconds = event.duration.total_seconds()
        if app_name in app_times:
            app_times[app_name] += duration_seconds
        else:
            app_times[app_name] = duration_seconds

    # Create DataFrame and sort by duration
    df = pd.DataFrame(list(app_times.items()), columns=['app_name', 'duration']).sort_values('duration',
                                                                                             ascending=False)
    df['duration_hours'] = df['duration'] / 3600

    return df


def create_app_usage_report(window_df, output_path, date_range_text):
    """Create HTML report with app usage pie chart"""
    # App usage pie chart - Top 10 apps
    top_apps = window_df.head(10).copy()
    other_time = window_df.iloc[10:]['duration'].sum() if len(window_df) > 10 else 0

    if other_time > 0:
        other_row = pd.DataFrame([{'app_name': 'Other', 'duration': other_time, 'duration_hours': other_time / 3600}])
        top_apps = pd.concat([top_apps, other_row], ignore_index=True)

    # Ensure duration is numeric and sort by duration
    top_apps['duration'] = pd.to_numeric(top_apps['duration'])
    top_apps = top_apps.sort_values('duration', ascending=False)
    
    # Calculate percentages
    total_app_time = top_apps['duration'].sum()
    top_apps['percentage'] = (top_apps['duration'] / total_app_time * 100).round(1)
    top_apps['label'] = top_apps.apply(lambda row: f"{row['app_name']}: {row['percentage']}%", axis=1)

    # Create custom pie chart using graph_objects for more control
    app_pie_fig = go.Figure(data=[go.Pie(
        labels=top_apps['app_name'],
        values=top_apps['duration'],
        text=top_apps['label'],
        textinfo='text',
        textposition='outside',
        hole=0.4
    )])
    
    app_pie_fig.update_layout(
        title=f"Application Usage ({date_range_text})",
        uniformtext_minsize=10,
        uniformtext_mode='hide'
    )

    # Write HTML file with the chart
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>ActivityWatch App Usage Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1, h2 {
            color: #333;
        }
        .chart {
            margin-bottom: 30px;
        }
        .summary {
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .footer {
            margin-top: 30px;
            text-align: center;
            color: #777;
            font-size: 0.9em;
        }
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="container">
        <h1>ActivityWatch App Usage Report</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p>Time period: ''' + date_range_text + '''</p>
            <p>Total app usage time: ''' + f"{total_app_time / 3600:.1f} hours" + '''</p>
        </div>

        <div class="chart">
            <h2>Application Usage Distribution</h2>
            ''' + app_pie_fig.to_html(full_html=False, include_plotlyjs=False) + '''
        </div>

        <div class="footer">
            <p>Generated on ''' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '''</p>
        </div>
    </div>
</body>
</html>''')

    print(f"Report generated successfully at {output_path}")


def get_current_week_dates():
    """Get the current week's start (Monday) and end (Sunday) dates"""
    today = datetime.now(timezone.utc)
    current_weekday = today.weekday()  # Monday is 0, Sunday is 6

    # If today is Monday, use today as start date
    if current_weekday == 0:  # Monday
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today
    else:
        # Today is not Monday, so just return today's data
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today

    return start_date, end_date, f"{start_date.strftime('%A, %b %d')} to {end_date.strftime('%A, %b %d')}"


def main():
    # Create command line arguments
    parser = argparse.ArgumentParser(description='Generate ActivityWatch app usage report')
    parser.add_argument('--days', type=int, default=None, help='Number of days to analyze (default: current week)')
    parser.add_argument('--output', type=str, default='C:/Users/vigge/.cursor/Moce-DV/Python/index.html',
                        help='Output file path (default: C:/Users/vigge/.cursor/Moce-DV/Python/index.html)')
    parser.add_argument('--weekly', action='store_true', help='Use current week (Monday to Sunday)')
    args = parser.parse_args()

    # Initialize client and date range
    client = ActivityWatchClient()

    # Determine date range - either current week or specified days
    if args.weekly or args.days is None:
        start_date, end_date, date_range_text = get_current_week_dates()
        days = (end_date - start_date).days + 1
    else:
        days = args.days
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        date_range_text = f"Past {days} days"

    print(f"Analyzing data from {start_date} to {end_date} ({date_range_text})")

    try:
        # Get specific bucket ID for window activity
        buckets = client.get_buckets()
        window_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-window_REX' in bid), None)
        
        if not window_bucket:
            print("Warning: Could not find window bucket with '_REX' suffix.")
            window_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-window' in bid), None)
            print(f"Using fallback window bucket: {window_bucket}")

        # Get window activity data
        window_df = get_window_activity(client, start_date, end_date, window_bucket)

        # Create report with just the app usage pie chart
        create_app_usage_report(window_df, args.output, date_range_text)

    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main() 