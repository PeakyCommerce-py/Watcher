from aw_client import ActivityWatchClient
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import os
import argparse
import json
import requests
import re


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


def get_web_activity(client, start_date, end_date, bucket_id=None):
    """Get web activity data and return as DataFrame"""
    if bucket_id is None:
        buckets = client.get_buckets()
        web_buckets = [bid for bid in buckets.keys() if 'aw-watcher-web' in bid]
        if not web_buckets:
            print("No web watcher buckets found, skipping web activity")
            return pd.DataFrame()
        bucket_id = web_buckets[0]
        print(f"Using web bucket: {bucket_id}")

    events = client.get_events(bucket_id, start=start_date, end=end_date)
    print(f"Found {len(events)} web events")

    website_times = {}
    for event in events:
        # Handle both dictionary and string data formats
        if isinstance(event.data, str):
            try:
                event_data = json.loads(event.data)
            except json.JSONDecodeError:
                event_data = {"title": "Unknown", "url": "Unknown"}
        else:
            event_data = event.data

        title = event_data.get('title', 'Unknown')
        url = event_data.get('url', 'Unknown')
        # Extract domain from URL
        domain = url.split('//')[-1].split('/')[0]
        duration_seconds = event.duration.total_seconds()

        key = domain
        if key in website_times:
            website_times[key] += duration_seconds
        else:
            website_times[key] = duration_seconds

    # Create DataFrame and sort by duration
    if website_times:
        df = pd.DataFrame(list(website_times.items()), columns=['website', 'duration']).sort_values('duration',
                                                                                                    ascending=False)
        df['duration_hours'] = df['duration'] / 3600
        return df
    return pd.DataFrame()


def get_afk_data(client, start_date, end_date, bucket_id=None):
    """Get AFK (away from keyboard) data"""
    if bucket_id is None:
        buckets = client.get_buckets()
        afk_buckets = [bid for bid in buckets.keys() if 'aw-watcher-afk' in bid]
        if not afk_buckets:
            raise Exception("No AFK watcher buckets found")
        bucket_id = afk_buckets[0]
        print(f"Using AFK bucket: {bucket_id}")

    events = client.get_events(bucket_id, start=start_date, end=end_date)
    print(f"Found {len(events)} AFK events")

    # Categorize time as AFK or active
    afk_time = 0
    active_time = 0

    for event in events:
        # Handle both dictionary and string data formats
        if isinstance(event.data, str):
            try:
                event_data = json.loads(event.data)
            except json.JSONDecodeError:
                event_data = {"status": "unknown"}
        else:
            event_data = event.data

        if event_data.get('status') == 'afk':
            afk_time += event.duration.total_seconds()
        else:
            active_time += event.duration.total_seconds()

    return {
        'afk_time': afk_time,
        'active_time': active_time,
        'afk_hours': afk_time / 3600,
        'active_hours': active_time / 3600
    }


def get_category_data(client, start_date, end_date, window_df=None, web_df=None):
    """Get categorized data from ActivityWatch"""
    # Productivity categories
    productive_categories = ['Work', 'Programming', 'Education', 'Productivity']
    unproductive_categories = ['Media', 'Games', 'Entertainment', 'Social Media', 'Uncategorized']

    try:
        # Try to get categorized events from ActivityWatch
        buckets = client.get_buckets()

        # First attempt: try to query for categorized events from QueryView
        try:
            # ActivityWatch Query - this is the proper way to query the API
            # Note that we can't use client.post directly as it doesn't exist

            # Get the server address from the client
            server_address = client.server_address

            # Set up the query
            query = {
                "timeperiods": [
                    {
                        "type": "timeperiod",
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    }
                ],
                "query": ["categorize"]
            }

            # Call the query endpoint directly
            url = f"{server_address}/api/0/query/"
            headers = {"Content-Type": "application/json"}

            response = requests.post(url, json=query, headers=headers)

            if response.status_code == 200:
                result = response.json()
                print("Successfully retrieved categorized events from ActivityWatch")

                # Process categories
                category_times = {}
                for event in result:
                    category = event.get('data', {}).get('category', 'Uncategorized')
                    duration = event.get('duration', 0)

                    if category in category_times:
                        category_times[category] += duration
                    else:
                        category_times[category] = duration

                # Create DataFrame
                if category_times:
                    df = pd.DataFrame(list(category_times.items()), columns=['category', 'duration']).sort_values(
                        'duration', ascending=False)
                    df['duration_hours'] = df['duration'] / 3600

                    # Add productivity classification
                    df['productivity'] = df['category'].apply(
                        lambda x: 'Productive' if x in productive_categories else 'Unproductive')

                    return df

        except Exception as e:
            print(f"Could not get categorized events via query API: {e}")

        # Second attempt: Try to get category data via ActivityWatch's rules directly
        try:
            # Get rule data directly from ActivityWatch's rules
            url = f"{client.server_address}/api/0/rules"
            response = requests.get(url)

            if response.status_code == 200:
                rules = response.json()
                print(f"Got {len(rules)} rules from ActivityWatch")

                # Now get all window events and apply the rules manually
                window_events = []
                for bucket_id in buckets:
                    if 'aw-watcher-window' in bucket_id:
                        window_events.extend(client.get_events(bucket_id, start=start_date, end=end_date))

                # Apply rules manually to events
                categorized_events = {}
                for event in window_events:
                    app_name = event.data.get('app', 'Unknown')
                    # Simple rule matching based on app name
                    category = 'Uncategorized'
                    for rule in rules:
                        if 'rule' in rule and 'type' in rule['rule'] and rule['rule']['type'] == 'regex':
                            if 'regex' in rule['rule'] and re.search(rule['rule']['regex'], app_name, re.IGNORECASE):
                                category = rule.get('category', 'Uncategorized')
                                break

                    duration = event.duration.total_seconds()
                    if category in categorized_events:
                        categorized_events[category] += duration
                    else:
                        categorized_events[category] = duration

                if categorized_events:
                    df = pd.DataFrame(list(categorized_events.items()), columns=['category', 'duration']).sort_values(
                        'duration', ascending=False)
                    df['duration_hours'] = df['duration'] / 3600
                    df['productivity'] = df['category'].apply(
                        lambda x: 'Productive' if x in productive_categories else 'Unproductive')
                    return df
        except Exception as e:
            print(f"Could not get categorized events from rules: {e}")

        # Third attempt: Use rules-based categorization based on app names
        if window_df is not None:
            # Define productivity rules (example rules, can be expanded)
            productive_apps = ['code', 'visual studio', 'excel', 'word', 'powerpoint', 'outlook', 'teams',
                               'chrome', 'edge', 'firefox', 'safari', 'notion', 'slack', 'terminal',
                               'powershell', 'cmd', 'intellij', 'pycharm', 'webstorm', 'rider', 'goland',
                               'jupyter', 'postman', 'figma', 'adobe', 'zoom', 'github', 'gitlab', 'bitbucket',
                               'stackoverflow', 'jira', 'confluence', 'cursor', 'vscode']

            unproductive_apps = ['youtube', 'netflix', 'disney+', 'hbo', 'spotify', 'steam', 'epic games',
                                 'discord', 'telegram', 'whatsapp', 'messenger', 'instagram', 'facebook',
                                 'twitter', 'tiktok', 'reddit', 'games', 'twitch', 'hulu', 'prime video']

            # Function to categorize app
            def categorize_app(app_name):
                app_lower = app_name.lower()
                for prod_app in productive_apps:
                    if prod_app.lower() in app_lower:
                        return 'Productive'
                for unprod_app in unproductive_apps:
                    if unprod_app.lower() in app_lower:
                        return 'Unproductive'
                return 'Uncategorized'

            # Add productivity category to window_df
            window_df['productivity'] = window_df['app_name'].apply(categorize_app)

            # Group by productivity
            productivity_df = window_df.groupby('productivity')['duration'].sum().reset_index()
            productivity_df['duration_hours'] = productivity_df['duration'] / 3600

            print("Created productivity categorization based on app names")
            return productivity_df

    except Exception as e:
        print(f"Error processing category data: {e}")

    # Fallback to basic empty DataFrame with productivity columns
    df = pd.DataFrame({'productivity': ['Productive', 'Unproductive', 'Uncategorized'],
                       'duration': [0, 0, 0],
                       'duration_hours': [0, 0, 0]})
    return df


def create_report(window_df, web_df, afk_data, category_df, output_path, date_range_text=None):
    """Create HTML report with visualizations"""
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
        title=f"Application Usage",
        uniformtext_minsize=10,
        uniformtext_mode='hide'
    )

    # Website pie chart if available
    if not web_df.empty:
        top_websites = web_df.head(10).copy()
        other_web_time = web_df.iloc[10:]['duration'].sum() if len(web_df) > 10 else 0

        if other_web_time > 0:
            other_web_row = pd.DataFrame(
                [{'website': 'Other', 'duration': other_web_time, 'duration_hours': other_web_time / 3600}])
            top_websites = pd.concat([top_websites, other_web_row], ignore_index=True)

        # Ensure duration is numeric and sort by duration
        top_websites['duration'] = pd.to_numeric(top_websites['duration'])
        top_websites = top_websites.sort_values('duration', ascending=False)

        # Calculate percentages
        total_web_time = top_websites['duration'].sum()
        top_websites['percentage'] = (top_websites['duration'] / total_web_time * 100).round(1)
        top_websites['label'] = top_websites.apply(lambda row: f"{row['website']}: {row['percentage']}%", axis=1)

        # Use graph_objects for website pie chart too
        web_pie_fig = go.Figure(data=[go.Pie(
            labels=top_websites['website'],
            values=top_websites['duration'],
            text=top_websites['label'],
            textinfo='text',
            textposition='outside',
            hole=0.4
        )])

        web_pie_fig.update_layout(
            title=f"Website Usage",
            uniformtext_minsize=10,
            uniformtext_mode='hide'
        )

        web_html = web_pie_fig.to_html(full_html=False, include_plotlyjs=False)
    else:
        web_html = "<p>No web activity data available.</p>"

    # AFK vs Active time
    total_tracked = afk_data['afk_time'] + afk_data['active_time']
    afk_percent = (afk_data['afk_time'] / total_tracked * 100) if total_tracked > 0 else 0
    active_percent = (afk_data['active_time'] / total_tracked * 100) if total_tracked > 0 else 0

    afk_fig = go.Figure()
    afk_fig.add_trace(go.Bar(
        x=['Computer Activity'],
        y=[afk_data['active_hours']],
        name='Active',
        marker_color='#2ca02c'
    ))
    afk_fig.add_trace(go.Bar(
        x=['Computer Activity'],
        y=[afk_data['afk_hours']],
        name='AFK',
        marker_color='#d62728'
    ))
    afk_fig.update_layout(
        barmode='stack',
        title=f"Active vs. AFK Time",
        yaxis=dict(title='Hours'),
        annotations=[
            dict(
                x='Computer Activity',
                y=afk_data['active_hours'] / 2,
                text=f"{active_percent:.1f}%",
                showarrow=False,
                font=dict(color='white')
            ),
            dict(
                x='Computer Activity',
                y=afk_data['active_hours'] + afk_data['afk_hours'] / 2,
                text=f"{afk_percent:.1f}%",
                showarrow=False,
                font=dict(color='white')
            )
        ]
    )

    # Productivity chart
    if 'productivity' in category_df.columns:
        # Ensure we have numeric values for duration
        category_df['duration'] = pd.to_numeric(category_df['duration'])

        # Group by productivity if it hasn't been done yet
        if len(category_df) > 2:  # Assuming there are more rows, we need to group
            productivity_df = category_df.groupby('productivity')['duration'].sum().reset_index()
        else:
            productivity_df = category_df.copy()

        # Make sure we have all three categories, adding zeros for missing ones
        all_categories = ['Productive', 'Unproductive', 'Uncategorized']
        for category in all_categories:
            if category not in productivity_df['productivity'].values:
                productivity_df = pd.concat([productivity_df,
                                             pd.DataFrame({'productivity': [category], 'duration': [0]})],
                                            ignore_index=True)

        # Calculate total time and percentages
        total_time = productivity_df['duration'].sum()
        if total_time > 0:
            productivity_df['percentage'] = (productivity_df['duration'] / total_time * 100).round(1)
            productivity_df['hours'] = productivity_df['duration'] / 3600
            productivity_df['label'] = productivity_df.apply(
                lambda row: f"{row['productivity']}: {row['percentage']}%", axis=1)

            # Create pie chart using go.Pie for better control
            colors = {'Productive': '#2ca02c', 'Unproductive': '#d62728', 'Uncategorized': '#7f7f7f'}
            productivity_fig = go.Figure(data=[go.Pie(
                labels=productivity_df['productivity'],
                values=productivity_df['duration'],
                text=productivity_df['label'],
                textinfo='text',
                textposition='outside',
                marker=dict(colors=[colors.get(p, '#7f7f7f') for p in productivity_df['productivity']]),
                hole=0.4
            )])

            productivity_fig.update_layout(
                title="Productivity Distribution",
                uniformtext_minsize=10,
                uniformtext_mode='hide'
            )

            productivity_html = productivity_fig.to_html(full_html=False, include_plotlyjs=False)

            # Create bar chart for productivity
            prod_bar_fig = go.Figure()

            for idx, row in productivity_df.iterrows():
                color = colors.get(row['productivity'], '#7f7f7f')
                prod_bar_fig.add_trace(go.Bar(
                    x=[row['productivity']],
                    y=[row['hours']],
                    name=row['productivity'],
                    marker_color=color,
                    text=f"{row['percentage']:.1f}%",
                    textposition='auto'
                ))

            prod_bar_fig.update_layout(
                title="Productivity Hours",
                yaxis=dict(title='Hours'),
                xaxis=dict(title='')
            )

            productivity_bar_html = prod_bar_fig.to_html(full_html=False, include_plotlyjs=False)
        else:
            productivity_html = "<p>No productivity data available.</p>"
            productivity_bar_html = "<p>No productivity data available.</p>"
    else:
        productivity_html = "<p>No productivity categorization available.</p>"
        productivity_bar_html = "<p>No productivity data available.</p>"

    # Top 10 apps bar chart
    bar_data = window_df.head(10).copy()
    bar_fig = px.bar(
        bar_data,
        x='app_name',
        y='duration_hours',
        title=f"Top 10 Applications by Time Spent",
        labels={'app_name': 'Application', 'duration_hours': 'Hours'},
        color_discrete_sequence=['#1f77b4']
    )
    bar_fig.update_layout(xaxis_tickangle=-45)

    # Write HTML file with all charts
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>ActivityWatch Usage Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1, h2 {{
            color: #333;
        }}
        .chart {{
            margin-bottom: 30px;
        }}
        .summary {{
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .toggle-section {{
            margin-bottom: 20px;
        }}
        .toggle-button {{
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }}
        .toggle-content {{
            display: none;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-top: 10px;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #777;
            font-size: 0.9em;
        }}
        .productivity-section {{
            margin-top: 30px;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }}
        .productive {{
            color: #2ca02c;
            font-weight: bold;
        }}
        .unproductive {{
            color: #d62728;
            font-weight: bold;
        }}
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        function toggleContent(id) {{
            var content = document.getElementById(id);
            if (content.style.display === "block") {{
                content.style.display = "none";
            }} else {{
                content.style.display = "block";
            }}
        }}

        // Show the default view when page loads
        window.onload = function() {{
            document.getElementById('productivity-content').style.display = "block";
        }}
    </script>
</head>
<body>
    <div class="container">
        <h1>ActivityWatch Usage Report</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p>Time period: {date_range_text}</p>
            <p>Total tracking time: {total_tracked / 3600:.1f} hours</p>
            <p>Active time: {afk_data['active_hours']:.1f} hours ({active_percent:.1f}%)</p>
            <p>AFK time: {afk_data['afk_hours']:.1f} hours ({afk_percent:.1f}%)</p>
        </div>

        <div class="toggle-section">
            <button class="toggle-button" onclick="toggleContent('productivity-content')">Toggle Productivity Chart</button>
            <div id="productivity-content" class="toggle-content">
                <h2>Productivity Overview</h2>
                {productivity_html}
                {productivity_bar_html}
            </div>
        </div>

        <div class="toggle-section">
            <button class="toggle-button" onclick="toggleContent('afk-content')">Toggle AFK/Active Chart</button>
            <div id="afk-content" class="toggle-content">
                <h2>AFK vs. Active Time</h2>
                {afk_fig.to_html(full_html=False, include_plotlyjs=False)}
            </div>
        </div>

        <div class="chart">
            <h2>Application Usage Distribution</h2>
            {app_pie_fig.to_html(full_html=False, include_plotlyjs=False)}
        </div>

        <div class="chart">
            <h2>Website Usage Distribution</h2>
            {web_html}
        </div>

        <div class="chart">
            <h2>Top Applications</h2>
            {bar_fig.to_html(full_html=False, include_plotlyjs=False)}
        </div>

        <div class="footer">
            <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>''')

    print(f"Report generated successfully at {output_path}")


def main():
    # Create command line arguments
    parser = argparse.ArgumentParser(description='Generate ActivityWatch usage report')
    parser.add_argument('--output', type=str, default='C:/Users/Dejan/PycharmProjects/watcher/Watcher 2/index.html',
                        help='Output file path (default: C:/Users/Dejan/PycharmProjects/watcher/Watcher 2/index.html)')
    parser.add_argument('--show-all-days', action='store_true',
                        help='Show all days of the week even if it is Monday')
    args = parser.parse_args()

    # Get current date and determine the start and end of current week
    today = datetime.now(timezone.utc)
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    start_date = datetime(start_of_week.year, start_of_week.month, start_of_week.day,
                          0, 0, 0, tzinfo=timezone.utc)

    # If today is Monday, only get today's data unless show-all-days is specified
    if today.weekday() == 0 and not args.show_all_days:  # Monday is 0
        end_date = today
        date_range_text = f"Today ({today.strftime('%A, %b %d')})"
    else:
        # Otherwise get data up to now
        end_date = today
        date_range_text = f"This week ({start_date.strftime('%A, %b %d')} to {today.strftime('%A, %b %d')})"

    print(f"Analyzing data from {start_date} to {end_date}")
    print(f"Date range: {date_range_text}")

    try:
        # Initialize client
        client = ActivityWatchClient()

        # Test connection to ActivityWatch
        try:
            response = requests.get(f"{client.server_address}/api/0/buckets")
            if response.status_code != 200:
                print(f"Warning: ActivityWatch server returned status code {response.status_code}")
        except Exception as e:
            print(f"Warning: Could not connect to ActivityWatch server: {e}")
            print("Make sure ActivityWatch is running and accessible.")

        # Get specific bucket IDs for your system (DESKTOP-FRC9TT4)
        buckets = client.get_buckets()
        window_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-window_DESKTOP-FRC9TT4' in bid), None)
        afk_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-afk_DESKTOP-FRC9TT4' in bid), None)
        web_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-web-opera_DESKTOP-FRC9TT4' in bid), None)

        if not window_bucket:
            print("Warning: Could not find window bucket with '_DESKTOP-FRC9TT4' suffix.")
            window_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-window' in bid), None)
            print(f"Using fallback window bucket: {window_bucket}")

        if not afk_bucket:
            print("Warning: Could not find AFK bucket with '_DESKTOP-FRC9TT4' suffix.")
            afk_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-afk' in bid), None)
            print(f"Using fallback AFK bucket: {afk_bucket}")

        if not web_bucket:
            print("Warning: Could not find web bucket with '_DESKTOP-FRC9TT4' suffix.")
            web_bucket = next((bid for bid in buckets.keys() if 'aw-watcher-web' in bid), None)
            print(f"Using fallback web bucket: {web_bucket}")

        # Get window activity data
        window_df = get_window_activity(client, start_date, end_date, window_bucket)

        # Get web activity data if available
        web_df = get_web_activity(client, start_date, end_date, web_bucket)

        # Get AFK data
        afk_data = get_afk_data(client, start_date, end_date, afk_bucket)

        # Get productivity categorized data
        category_df = get_category_data(client, start_date, end_date, window_df, web_df)

        # Create report
        create_report(window_df, web_df, afk_data, category_df, args.output, date_range_text)

    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()