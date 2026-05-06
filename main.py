import os
import json
import mimetypes
import requests
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import OpenAI

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")

LATITUDE = os.getenv("LATITUDE", "34.2073")
LONGITUDE = os.getenv("LONGITUDE", "-84.1402")
LOCATION_NAME = os.getenv("LOCATION_NAME", "Cumming, GA")
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
BACKGROUND_IMAGE_PATH = os.getenv("BACKGROUND_IMAGE_PATH", "images/cloud-bg.jpeg")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing.")

if not EMAIL_USER:
    raise ValueError("EMAIL_USER is missing.")

if not EMAIL_PASSWORD:
    raise ValueError("EMAIL_PASSWORD is missing.")

if not TO_EMAIL:
    raise ValueError("TO_EMAIL is missing.")

client = OpenAI(api_key=OPENAI_API_KEY)


def get_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}"
        f"&longitude={LONGITUDE}"
        "&current=temperature_2m,weather_code,is_day"
        "&temperature_unit=fahrenheit"
    )

    response = requests.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()

    current = data["current"]
    return {
        "temperature": current["temperature_2m"],
        "weather_code": current.get("weather_code"),
        "is_day": current.get("is_day", 1),
    }


def get_local_context():
    now = datetime.now(ZoneInfo(TIMEZONE))
    hour = now.hour
    month = now.month

    if 5 <= hour < 12:
        greeting = "Good morning"
        part_of_day = "morning"
    elif 12 <= hour < 17:
        greeting = "Good afternoon"
        part_of_day = "afternoon"
    elif 17 <= hour < 21:
        greeting = "Good evening"
        part_of_day = "evening"
    else:
        greeting = "Hello"
        part_of_day = "night"

    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "fall"

    return {
        "greeting": greeting,
        "part_of_day": part_of_day,
        "season": season,
        "current_time": now.strftime("%I:%M %p").lstrip("0"),
        "weekday": now.strftime("%A"),
        "date_text": now.strftime("%B %d, %Y"),
    }


def describe_temperature(temp_f):
    if temp_f < 40:
        return "very cold"
    if temp_f < 55:
        return "cool"
    if temp_f < 70:
        return "pleasant"
    if temp_f < 82:
        return "warm"
    return "hot"


def weather_code_to_text(code):
    mapping = {
        0: "clear skies",
        1: "mostly clear skies",
        2: "partly cloudy skies",
        3: "overcast skies",
        45: "foggy conditions",
        48: "foggy conditions",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        56: "freezing drizzle",
        57: "freezing drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        66: "freezing rain",
        67: "freezing rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        77: "snow grains",
        80: "rain showers",
        81: "rain showers",
        82: "heavy rain showers",
        85: "snow showers",
        86: "heavy snow showers",
        95: "thunderstorms",
        96: "thunderstorms with hail",
        99: "strong thunderstorms with hail",
    }
    return mapping.get(code, "current weather conditions")


def get_theme_colors(part_of_day, season):
    themes = {
        ("morning", "spring"): {"accent": "#ff8c42", "soft": "#fff4ea", "text": "#1f2937"},
        ("morning", "summer"): {"accent": "#fb8500", "soft": "#fff6dd", "text": "#1f2937"},
        ("morning", "fall"): {"accent": "#e76f51", "soft": "#fff1ea", "text": "#3d2c29"},
        ("morning", "winter"): {"accent": "#3b82f6", "soft": "#eef6ff", "text": "#1f2a44"},
        ("afternoon", "spring"): {"accent": "#22c55e", "soft": "#effff5", "text": "#1f2937"},
        ("afternoon", "summer"): {"accent": "#f77f00", "soft": "#fff7db", "text": "#2b2d42"},
        ("afternoon", "fall"): {"accent": "#d97706", "soft": "#fff4e5", "text": "#3d2c29"},
        ("afternoon", "winter"): {"accent": "#2563eb", "soft": "#eef4ff", "text": "#1f2a44"},
        ("evening", "spring"): {"accent": "#9d4edd", "soft": "#faf2ff", "text": "#2b2d42"},
        ("evening", "summer"): {"accent": "#e76f51", "soft": "#fff1ed", "text": "#2f2f46"},
        ("evening", "fall"): {"accent": "#c8553d", "soft": "#fff0ea", "text": "#2d1e2f"},
        ("evening", "winter"): {"accent": "#3a86ff", "soft": "#edf8ff", "text": "#1f2937"},
        ("night", "spring"): {"accent": "#7b2cbf", "soft": "#f7f0ff", "text": "#2b2d42"},
        ("night", "summer"): {"accent": "#118ab2", "soft": "#eef9ff", "text": "#203040"},
        ("night", "fall"): {"accent": "#9c6644", "soft": "#fff5ef", "text": "#33272a"},
        ("night", "winter"): {"accent": "#60a5fa", "soft": "#edf5ff", "text": "#1f2937"},
    }
    return themes.get((part_of_day, season), {"accent": "#2563eb", "soft": "#eff6ff", "text": "#1f2937"})


def create_ai_content(location_name, temp_f, weather_text, context):
    temp_feel = describe_temperature(temp_f)

    prompt = f"""
You are an intelligent weather email writer.

Your job is to generate a short, warm, visually-friendly weather email content that matches the actual trigger context.

Context:
- location: {location_name}
- local time: {context["current_time"]}
- day of week: {context["weekday"]}
- date: {context["date_text"]}
- part of day: {context["part_of_day"]}
- greeting: {context["greeting"]}
- season: {context["season"]}
- current temperature in Fahrenheit: {temp_f}
- weather description: {weather_text}
- temperature feel: {temp_feel}

Instructions:
- The email must feel aware of the actual local time when the agent runs.
- If it is evening, do not say "Good morning."
- If it is night, do not use daytime language.
- Write in a polished, friendly, human tone.
- Keep it concise and useful.
- Mention the weather naturally, not like a raw API response.
- Include one practical tip or suggestion relevant to the weather and time of day.
- Make the content suitable for a colorful HTML email with a sky/cloud background.
- Do not mention internal logic, JSON, API, or model behavior.

Return valid JSON only in this exact format:
{{
  "subject": "string",
  "headline": "string",
  "message": "string",
  "tip": "string"
}}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    raw_text = response.output_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "subject": f"Daily Weather Reminder - {location_name}",
            "headline": f'{context["greeting"]}, {location_name}!',
            "message": f"It’s currently {temp_f}°F with {weather_text}, making for a {temp_feel} {context['part_of_day']}.",
            "tip": "Dress comfortably and plan any outdoor time around the current conditions.",
        }


def build_html_email(content, location_name, temp_f, weather_text, context, theme):
    subject = content.get("subject", f"Daily Weather Reminder - {location_name}")
    headline = content.get("headline", f'{context["greeting"]}, {location_name}!')
    message = content.get("message", "")
    tip = content.get("tip", "")

    accent = theme["accent"]
    soft = theme["soft"]
    text = theme["text"]

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{subject}</title>
</head>
<body style="margin:0; padding:0; background-color:#eef4f8; font-family:Arial, Helvetica, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#eef4f8; margin:0; padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="680" cellspacing="0" cellpadding="0" border="0" style="max-width:680px; width:100%; background-color:#ffffff; border-radius:20px; overflow:hidden;">
          <tr>
            <td background="cid:skybg"
                style="background-image:url('cid:skybg'); background-size:cover; background-position:center; background-repeat:no-repeat; padding:0;">
              <div style="background:linear-gradient(rgba(17,24,39,0.30), rgba(17,24,39,0.45)); padding:36px 32px 42px 32px;">
                <div style="font-size:13px; letter-spacing:1px; text-transform:uppercase; color:#ffffff; font-weight:bold;">
                  Daily Weather Reminder
                </div>

                <div style="font-size:34px; line-height:1.25; font-weight:bold; color:#ffffff; margin-top:12px;">
                  {headline}
                </div>

                <div style="font-size:15px; line-height:1.6; color:#f8fafc; margin-top:10px;">
                  {context["weekday"]}, {context["date_text"]} • {context["current_time"]} • {location_name}
                </div>
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 28px 30px 28px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                     style="background:{soft}; border-left:5px solid {accent}; border-radius:14px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <div style="font-size:14px; color:{text}; font-weight:bold; margin-bottom:6px;">
                      Current weather
                    </div>
                    <div style="font-size:30px; color:{accent}; font-weight:bold;">
                      {temp_f}°F
                    </div>
                    <div style="font-size:15px; color:{text}; margin-top:6px; line-height:1.6;">
                      {weather_text.capitalize()} • {context["season"].capitalize()} • {context["part_of_day"].capitalize()}
                    </div>
                  </td>
                </tr>
              </table>

              <div style="font-size:16px; line-height:1.85; color:{text}; margin-top:24px;">
                {message}
              </div>

              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                     style="margin-top:24px; border:1px solid #e5e7eb; border-radius:14px; background:#f8fafc;">
                <tr>
                  <td style="padding:18px 20px;">
                    <div style="font-size:14px; color:{accent}; font-weight:bold; margin-bottom:8px;">
                      Helpful tip
                    </div>
                    <div style="font-size:15px; line-height:1.75; color:{text};">
                      {tip}
                    </div>
                  </td>
                </tr>
              </table>

              <div style="margin-top:26px; font-size:13px; color:#6b7280; text-align:center;">
                Sent thoughtfully for {location_name}
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def build_plain_text_email(content, location_name, temp_f, weather_text, context):
    subject = content.get("subject", f"Daily Weather Reminder - {location_name}")
    headline = content.get("headline", f'{context["greeting"]}, {location_name}!')
    message = content.get("message", "")
    tip = content.get("tip", "")

    return f"""{headline}

{context["weekday"]}, {context["date_text"]} • {context["current_time"]}
Location: {location_name}

Current weather: {temp_f}°F, {weather_text}

{message}

Helpful tip: {tip}

{subject}
"""


def attach_inline_image(msg_root, image_path, content_id):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Background image not found: {image_path}")

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Unsupported image file: {image_path}")

    with open(image_path, "rb") as f:
        img_data = f.read()

    image_part = MIMEImage(img_data)
    image_part.add_header("Content-ID", f"<{content_id}>")
    image_part.add_header("Content-Disposition", "inline", filename=os.path.basename(image_path))
    msg_root.attach(image_part)


def send_email(subject, plain_text_body, html_body, background_image_path):
    recipients = [email.strip() for email in TO_EMAIL.split(",") if email.strip()]

    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = subject
    msg_root["From"] = EMAIL_USER
    msg_root["To"] = ", ".join(recipients)

    msg_alternative = MIMEMultipart("alternative")
    msg_root.attach(msg_alternative)

    msg_alternative.attach(MIMEText(plain_text_body, "plain"))
    msg_alternative.attach(MIMEText(html_body, "html"))

    attach_inline_image(msg_root, background_image_path, "skybg")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, recipients, msg_root.as_string())


def main():
    weather = get_weather()
    context = get_local_context()

    temp_f = weather["temperature"]
    weather_text = weather_code_to_text(weather["weather_code"])
    theme = get_theme_colors(context["part_of_day"], context["season"])

    ai_content = create_ai_content(
        location_name=LOCATION_NAME,
        temp_f=temp_f,
        weather_text=weather_text,
        context=context,
    )

    subject = ai_content.get("subject", f"Daily Weather Reminder - {LOCATION_NAME}")
    html_body = build_html_email(ai_content, LOCATION_NAME, temp_f, weather_text, context, theme)
    plain_text_body = build_plain_text_email(ai_content, LOCATION_NAME, temp_f, weather_text, context)

    send_email(subject, plain_text_body, html_body, BACKGROUND_IMAGE_PATH)
    print("Weather email sent successfully.")


if __name__ == "__main__":
    main()