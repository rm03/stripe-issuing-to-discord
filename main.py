import stripe, requests, os, json
from flask import Flask, request
from datetime import datetime
from pytz import timezone

with open("config.json") as c:
    config = json.load("c")

API_KEY=config['stripe_api_key']
WH_SEC=config['stripe_webhook_secret']
AUTH_DECLINE_WH=config['authorization_decline_webhook']
REV_CAPT_WH=config['reversal_capture_webhook']

def formatPrint(cents):
    try:
        return "$"+str(cents)[:-2]+"."+str(cents)[-2:]
    except:
        return str(cents)+" cents"

def parseTimestamp(ts):
    #Set to EST
    fmt = "%a %b %d %H:%M:%S %Z"
    dt_object=datetime.fromtimestamp(ts)
    eastern_time=dt_object.astimezone(timezone('US/Eastern'))
    return eastern_time.strftime(fmt)

app = Flask(__name__)
stripe.api_key = API_KEY

@app.route("/webhook", methods=["POST"])

def webhooks():
    payload = request.data.decode("utf-8")
    received_sig = request.headers.get("Stripe-Signature", None)

    try:
        event = stripe.Webhook.construct_event(
            payload, received_sig, WH_SEC
        )
    except ValueError:
        print("Error while decoding event!")
        return "Bad payload", 400
    except stripe.error.SignatureVerificationError:
        print("Invalid signature!")
        return "Bad signature", 400
    print(event)

    if event["type"] == "issuing_authorization.created" or event["type"]=="issuing_authorization.updated":
        charge_authorized=False
        charge_declined=False
        charge_reversed=False
        charge_settled=False
        timestamp=event['created']
        if event['data']['object']['approved']:
            if event["type"] == "issuing_authorization.created":
                charge_authorized=True
                title = "Charge Authorized"
                color = 9567854
                amount = formatPrint(event['data']['object']['amount'])
            else:
                if event['data']['object']['status']=="reversed":   
                    charge_reversed=True
                    title = "Charge Reversed"
                    color = 16316286
                    amount = formatPrint(event['data']['previous_attributes']['amount'])
                elif event['data']['object']['status']=="closed":
                    charge_settled=True
                    title = "Charge Settled"
                    color = 2420223
                    amount = formatPrint(event['data']['object']['amount'])
            transaction_id={
	        	"name": "Transaction ID",
                "value": "||"+event['data']['object']['id']+"||",
                "inline": False
	        }
        else:
            charge_declined=True
            title = "Charge Declined"
            color = 16674414
            amount = formatPrint(event['data']['object']['amount'])
            reason={
                "name": "Reason",
                "value": "||"+event['data']['object']['request_history'][0]['reason']+"||",
                "inline": False
            }
        if charge_authorized==True or charge_declined==True:
            discord_wh=AUTH_DECLINE_WH
        else:
            discord_wh=REV_CAPT_WH
        json={
        "embeds": [
            {
            "title": title,
            "description": f"**{event['data']['object']['merchant_data']['name']}** - {event['data']['object']['merchant_data']['city']}, {event['data']['object']['merchant_data']['state']}",
            "color": color,
            "fields": [
                {
                    "name": "Amount",
                    "value": amount,
                    "inline": True
                },
                {
                    "name": "Card Holder",
                    "value": f"||{event['data']['object']['card']['cardholder']['name'].split(' ')[0]}||",
                    "inline": True
                },
                {
                    "name": "Last Four",
                    "value": "||"+event['data']['object']['card']['last4']+"||",
                    "inline": True
                }
            ],
            "footer": {
                "text": parseTimestamp(timestamp),
                "icon_url": "https://pbs.twimg.com/profile_images/1280236709825835008/HmeYTwai_400x400.png"
            }
            }
        ]
        }
        if charge_declined:
            json["embeds"][0]["fields"].append(reason)
        else:
        	json["embeds"][0]["fields"].append(transaction_id)
        requests.post(discord_wh, json=json)
        return "", 200

if __name__ == '__main__':
	app.run(debug=True)