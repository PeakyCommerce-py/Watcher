#!/usr/bin/env python3
"""
ActivityWatch Data Export and Visualization Script
This script exports data from ActivityWatch and creates visualizations.
"""
from aw_client import ActivityWatchClient
from datetime import datetime, timedelta
import json
from collections import defaultdict
import pytz
import argparse
import re
from dateutil.parser import parse as parse_date
import os
import sys
import io

# Set up UTF-8 output encoding for Windows compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_category_rules(json_file='aw-category-export.json'):
    """Load category rules from the exported JSON file."""
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, json_file)

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        rules = []
        for category in data['categories']:
            if category['rule']['type'] == 'regex' and 'regex' in category['rule']:
                rules.append({
                    'name': category['name'],
                    'regex': category['rule']['regex'],
                    'ignore_case': category['rule'].get('ignore_case', False)
                })
        return rules
    except FileNotFoundError:
        print(f"\nWarning: Category rules file not found at {json_path}")
        print("Creating default category rules...")
        default_rules = {
            'categories': [
                {
                    'name': 'Work',
                    'rule': {'type': 'regex', 'regex': '(code|visual studio|intellij|pycharm|cursor|github|gitlab)', 'ignore_case': True}
                },
                {
                    'name': 'Media',
                    'rule': {'type': 'regex', 'regex': '(youtube|netflix|spotify|game|steam|epic|origin)', 'ignore_case': True}
                }
            ]
        }

        # Save default rules
        with open(json_path, 'w') as f:
            json.dump(default_rules, f, indent=2)

        return load_category_rules(json_file)  # Try loading again


def categorize_event(event, rules):
    """Categorize an event using the loaded rules."""
    title = event['data'].get('title', '')
    app = event['data'].get('app', '')
    text = f"{app} {title}"

    for rule in rules:
        pattern = rule['regex']
        flags = re.IGNORECASE if rule.get('ignore_case', False) else 0
        if re.search(pattern, text, flags=flags):
            return rule['name']

    return ['Uncategorized']


# Replace the timezone section in the update_index_html_timestamp function
# with this code

def update_index_html_timestamp(data):
    """Update the last update time in index.html."""
    try:
        print("\nUpdating index.html with direct time display...")
        with open("index.html", "r", encoding='utf-8') as f:
            html_content = f.read()

        # IMPORTANT: Get current time with a +4 UTC offset (adjust this value as needed)
        # This directly sets the timezone offset rather than using a named
        # timezone
        from datetime import datetime, timedelta

        # Get UTC time
        utc_now = datetime.utcnow()

        # Apply a direct UTC offset - adjust the number here
        # +2 = UTC+2, +3 = UTC+3, +4 = UTC+4
        # Try +4 since you're 2 hours ahead of what's showing
        local_time = utc_now + timedelta(hours=2)

        # Format the time as YYYY-MM-DD HH:MM (24-hour format)
        current_time = local_time.strftime("%Y-%m-%d %H:%M")

        print(f"Using direct UTC+4 offset time: {current_time}")

        # Update the last update time
        if '<div class="last-update">' in html_content:
            # Replace existing update div
            new_html_content = re.sub(
                r'<div class="last-update">.*?</div>',
                f'<div class="last-update">Updated at: {current_time}</div>',
                html_content,
                flags=re.DOTALL
            )
        else:
            # Add new update div after the h1 title
            new_html_content = re.sub(
                r'(<h1>ActivityWatch Data Visualizations</h1>)',
                f'\\1\n        <div class="last-update">Updated at: {current_time}</div>',
                html_content
            )

        # Write the updated HTML back to the file
        with open("index.html", "w", encoding='utf-8') as f:
            f.write(new_html_content)

        print(f"✓ Successfully updated index.html with time: {current_time}")
        return True
    except Exception as e:
        print(f"Error updating index.html: {str(e)}")
        return False


def write_data_js(data):
    """Write activity data to data.js file."""
    try:
        print("\nWriting data to data.js...")
        with open("data.js", "w") as f:
            f.write(f"const activityData = {json.dumps(data, indent=2)};")
        print("✓ Successfully wrote data.js")
        return True
    except Exception as e:
        print(f"Error writing data.js: {str(e)}")
        return False


def process_event_timestamp(timestamp):
    """Process event timestamp with correct timezone adjustment."""
    # Parse the timestamp
    dt = datetime.fromisoformat(timestamp)

    # Apply a 2-hour adjustment to correct the timezone difference
    adjusted_dt = dt + timedelta(hours=1)

    return adjusted_dt


# Modify the main function to include both weekly and daily views

def main():
    """Main function to run the ActivityWatch data export and visualization."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Export ActivityWatch data to visualizations')
    parser.add_argument('--host', default='DESKTOP-FRC9TT4',
                        help='Host to query (e.g., DESKTOP-FRC9TT4 or DESKTOP-FRC9TT4-MacBook-Pro.local)')
    parser.add_argument('--date', help='Date to analyze (YYYY-MM-DD)')
    args = parser.parse_args()

    # Load category rules
    category_rules = load_category_rules()

    # Initialize client
    client = ActivityWatchClient("chart-client")

    # List available buckets
    buckets = client.get_buckets()
    print("\nAvailable buckets:")
    for bucket_id in buckets:
        print(f"- {bucket_id}")

    # Set the host
    HOST = args.host

    # Find web bucket
    web_bucket = None
    for bucket_id in buckets:
        if bucket_id.startswith("aw-watcher-web"):
            web_bucket = bucket_id
            break

    if web_bucket:
        print(f"\nFound web bucket: {web_bucket}")
    else:
        print("\nNo web bucket found")

    # Get current time in UTC
    current_time = datetime.now(pytz.UTC)

    # Get data for the week (Monday to now)
    days_since_monday = current_time.weekday()
    week_start_time = current_time - timedelta(days=days_since_monday)
    week_start_time = week_start_time.replace(
        hour=0, minute=0, second=0, microsecond=0)
    week_end_time = current_time

    # Get data for today
    today_start_time = current_time.replace(
        hour=0, minute=0, second=0, microsecond=0)
    today_end_time = current_time

    # Process weekly data
    print(f"\nQuerying weekly data:")
    print(
        f"Time period: {week_start_time.strftime('%A, %b %d, %Y')} to {week_end_time.strftime('%A, %b %d, %Y')}")
    weekly_data = process_time_period(
        client,
        HOST,
        web_bucket,
        week_start_time,
        week_end_time,
        category_rules)

    # Process today's data
    print(f"\nQuerying today's data:")
    print(
        f"Time period: {today_start_time.strftime('%A, %b %d, %Y')} to {today_end_time.strftime('%A, %b %d, %Y')}")
    daily_data = process_time_period(
        client,
        HOST,
        web_bucket,
        today_start_time,
        today_end_time,
        category_rules)

    # Create the combined data object
    combined_data = {
        "weekly": weekly_data,
        "daily": daily_data
    }

    # Write data to JavaScript file
    try:
        print("\nWriting data to data.js...")
        with open("data.js", "w") as f:
            f.write(
                f"const activityData = {json.dumps(combined_data, indent=2)};")
        print("✓ Successfully wrote data.js")
    except Exception as e:
        print(f"Error writing data.js: {str(e)}")
        raise

    # Update the HTML file
    update_index_html_timestamp(combined_data)

    print("\n✓ Data has been updated successfully!")
    print("  Open 'index.html' in a browser to view the activity charts and statistics.")


# Add this new function to process a specific time period
def process_time_period(client, HOST, web_bucket,
                        start_time, end_time, category_rules):
    """Process activity data for a specific time period."""
    # Define the query to get window events
    query = f"""
    afk_events = query_bucket(find_bucket("aw-watcher-afk_{HOST}"));
    window_events = query_bucket(find_bucket("aw-watcher-window_{HOST}"));
    window_events = filter_period_intersect(window_events, filter_keyvals(afk_events, "status", ["not-afk"]));
    RETURN = sort_by_duration(window_events);
    """

    # Add web activity query if web bucket is found
    web_query = None
    if web_bucket:
        web_query = f"""
        afk_events = query_bucket(find_bucket("aw-watcher-afk_{HOST}"));
        web_events = query_bucket("{web_bucket}");
        web_events = filter_period_intersect(web_events, filter_keyvals(afk_events, "status", ["not-afk"]));
        RETURN = sort_by_duration(web_events);
        """

    try:
        # Execute queries
        result = client.query(query, [(start_time, end_time)])
        events = result[0]

        # Get web events if web bucket exists
        web_events = []
        if web_query:
            web_result = client.query(web_query, [(start_time, end_time)])
            web_events = web_result[0]

        # Process the categorized events
        daily_data = defaultdict(
            lambda: {
                "productive": 0,
                "non_productive": 0,
                "other": 0,
                "afk": 0})
        app_time = defaultdict(lambda: {"duration": 0, "category": None})
        category_time = defaultdict(float)
        hourly_activity = defaultdict(float)
        web_time = defaultdict(float)  # Dictionary for web activity

        # Process web events
        if web_events:
            print(f"Found {len(web_events)} web events")

            for event in web_events:
                # Get timestamp and duration with timezone correction
                timestamp = process_event_timestamp(event['timestamp'])
                duration = event['duration']

                # Skip very short events (less than 1 second)
                if duration < 1:
                    continue

                # Get URL and title
                url = event['data'].get('url', '')
                title = event['data'].get('title', '')

                # Extract domain from URL
                try:
                    domain = url.split(
                        '/')[2] if len(url.split('/')) > 2 else url
                    # Clean up domain (remove www. and common TLDs)
                    domain = domain.replace('www.', '')
                    # Take just the main domain name
                    domain = domain.split('.')[0]
                except BaseException:
                    domain = url

                # Print significant web events (more than 5 minutes)
                if duration > 300:
                    print(f"\nSignificant web event:")
                    print(f"Domain: {domain}")
                    print(f"Title: {title}")
                    print(f"Duration: {duration / 3600:.2f} hours")

                # Update web statistics
                web_time[domain] += duration

        # Process window events
        print(f"Found {len(events)} events")

        for event in events:
            # Get timestamp and duration with timezone correction
            timestamp = process_event_timestamp(event['timestamp'])
            duration = event['duration']

            # Skip very short events (less than 1 second)
            if duration < 1:
                continue

            day = timestamp.date()

            # Update hourly activity
            hour = timestamp.hour
            hourly_activity[hour] += duration

            # Get app and category information
            app = event['data'].get('app', 'Unknown')
            title = event['data'].get('title', '')
            categories = categorize_event(event, category_rules)

            # Print significant events (more than 5 minutes)
            if duration > 300:
                print(f"\nSignificant event:")
                print(f"App: {app}")
                print(f"Title: {title}")
                print(
                    f"Categories: {' > '.join(categories) if categories else 'Uncategorized'}")
                print(f"Duration: {duration / 3600:.2f} hours")

            # Update app statistics
            app_time[app]['duration'] += duration
            if categories:
                app_time[app]['category'] = categories[0]

            # Update category statistics
            if categories:
                # Store full category path
                category_path = ' > '.join(categories)
                category_time[category_path] += duration

                # Update daily statistics based on top-level category
                if categories[0] == 'Work':
                    daily_data[day]["productive"] += duration
                elif categories[0] == 'Media':
                    daily_data[day]["non_productive"] += duration
                else:
                    daily_data[day]["other"] += duration

        # Get AFK time
        afk_query = f"""
        afk_events = query_bucket(find_bucket("aw-watcher-afk_{HOST}"));
        RETURN = filter_keyvals(afk_events, "status", ["afk"]);
        """
        afk_result = client.query(afk_query, [(start_time, end_time)])
        afk_events = afk_result[0]

        # Process AFK events
        for event in afk_events:
            timestamp = process_event_timestamp(event['timestamp'])
            duration = event['duration']
            day = timestamp.date()
            daily_data[day]["afk"] += duration

        # Calculate summary statistics
        total_active_seconds = sum(
            data["productive"] + data["non_productive"] + data["other"]
            for data in daily_data.values()
        )
        total_afk_seconds = sum(data["afk"] for data in daily_data.values())
        total_seconds = total_active_seconds + total_afk_seconds

        # Convert to hours
        total_hours = total_seconds / 3600
        active_hours = total_active_seconds / 3600
        afk_hours = total_afk_seconds / 3600

        productive_seconds = sum(data["productive"]
                                 for data in daily_data.values())
        non_productive_seconds = sum(
            data["non_productive"] for data in daily_data.values())
        other_seconds = sum(data["other"] for data in daily_data.values())

        productive_hours = productive_seconds / 3600
        non_productive_hours = non_productive_seconds / 3600
        other_hours = other_seconds / 3600

        # Calculate percentages
        active_percentage = (
            total_active_seconds /
            total_seconds *
            100) if total_seconds > 0 else 0
        afk_percentage = (
            total_afk_seconds /
            total_seconds *
            100) if total_seconds > 0 else 0
        productive_percentage = (
            productive_seconds /
            total_active_seconds *
            100) if total_active_seconds > 0 else 0
        non_productive_percentage = (
            non_productive_seconds / total_active_seconds * 100) if total_active_seconds > 0 else 0
        other_percentage = (
            other_seconds /
            total_active_seconds *
            100) if total_active_seconds > 0 else 0

        # Get top 5 apps
        top_apps = sorted(
            app_time.items(),
            key=lambda x: x[1]["duration"],
            reverse=True)[
            :5]

        # Get top 5 web domains
        top_web = sorted(
            web_time.items(),
            key=lambda x: x[1],
            reverse=True)[
            :5] if web_time else []

        # Generate hour data
        hour_data = [0] * 24
        for h in range(24):
            # Apply the 2-hour shift to the hour index (with wraparound)
            adjusted_h = (h + 2) % 24
            hour_data[adjusted_h] = hourly_activity[h] / \
                3600 if h in hourly_activity else 0

        # Sort categories by duration
        sorted_categories = sorted(
            category_time.items(),
            key=lambda x: x[1],
            reverse=True)

        # Prepare visualization data
        data = {
            "start_date": start_time.strftime("%A, %b %d, %Y"),
            "end_date": end_time.strftime("%A, %b %d, %Y"),
            "total_hours": total_hours,
            "active_hours": active_hours,
            "active_percentage": active_percentage,
            "afk_hours": afk_hours,
            "afk_percentage": afk_percentage,
            "productive_hours": productive_hours,
            "productive_percentage": productive_percentage,
            "non_productive_hours": non_productive_hours,
            "non_productive_percentage": non_productive_percentage,
            "other_hours": other_hours,
            "other_percentage": other_percentage,
            "labels": [str(day) for day in daily_data.keys()],
            "productive": [daily_data[day]["productive"] / 3600 for day in daily_data.keys()],
            "non_productive": [daily_data[day]["non_productive"] / 3600 for day in daily_data.keys()],
            "other": [daily_data[day]["other"] / 3600 for day in daily_data.keys()],
            "afk": [daily_data[day]["afk"] / 3600 for day in daily_data.keys()],
            "top_apps_labels": [app[0] for app in top_apps],
            "top_apps_data": [app[1]["duration"] / 3600 for app in top_apps],
            "top_apps_colors": [
                '#4CAF50' if app[1]["category"] == "Work" else
                '#FF5722' if app[1]["category"] == "Media" else
                '#FFC107'
                for app in top_apps
            ],
            "trend_labels": [str(day) for day in daily_data.keys()],
            "trend_data": [daily_data[day]["productive"] / 3600 for day in daily_data.keys()],
            "hour_labels": [f"{h}:00" for h in range(24)],
            "hour_data": hour_data,
            "categories": [cat[0] for cat in sorted_categories],
            "category_data": [cat[1] / 3600 for cat in sorted_categories],
            "category_colors": [
                '#4CAF50' if cat[0].startswith('Work') else
                '#FF5722' if cat[0].startswith('Media') else
                '#FFC107'
                for cat in sorted_categories
            ],
            "web_labels": [web[0] for web in top_web],
            "web_data": [web[1] / 3600 for web in top_web],
            "web_colors": [
                '#4CAF50' if any(
                    work_domain in web[0].lower() for work_domain in ['github', 'stackoverflow', 'docs.google']) else
                '#FF5722' if any(
                    media_domain in web[0].lower() for media_domain in ['youtube', 'netflix', 'spotify']) else
                '#FFC107'
                for web in top_web
            ] if top_web else []
        }

        # Print summary
        print("\nData Collection Summary:")
        print(f"- Total tracking time: {total_hours:.1f} hours")
        print(
            f"- Active time: {active_hours:.1f} hours ({active_percentage:.1f}%)")
        print(f"- AFK time: {afk_hours:.1f} hours ({afk_percentage:.1f}%)")
        print(
            f"- Productive time: {productive_hours:.1f} hours ({productive_percentage:.1f}% of active time)")
        print(
            f"- Non-productive time: {non_productive_hours:.1f} hours ({non_productive_percentage:.1f}% of active time)")
        print(
            f"- Other time: {other_hours:.1f} hours ({other_percentage:.1f}% of active time)")

        return data

    except Exception as e:
        print(f"\nError executing query: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Error message received: {e.response.text}")
        raise


if __name__ == "__main__":
    main()
