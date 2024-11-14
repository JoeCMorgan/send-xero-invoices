### New Droplet setup
* Run `sudo apt-get update`
* Run `sudo apt-get -y upgrade`
* Run `sudo apt-get install -y python3-pip`
* Run `sudo apt-get install build-essential libssl-dev libffi-dev python3-dev`
* Run `sudo apt-get install -y python3-venv`

### Set up the virtual env
* Run `mkdir invoice_emails`
* Run `cd invoice_emails`
* Create new python virtual environment by running `python3 -m venv invoice_emails_env`
* Activate new virtual environment by running `source invoice_emails_env/bin/activate`
* Clone the repo `git clone https://github.com/JoeCMorgan/send-xero-invoices.git`
* Install xero-python by running `pip install xero-python`
* Install dotenv by running `pip install python-dotenv`
* Create the `.env` file containing Xero and SMTP keys in the root `send-xero-invoices` folder:
```
XERO_TOKEN = ""
CLIENT_ID = ""
CLIENT_SECRET = ""
TENANT_ID = ""

SMTP_SERVER = ""
SMTP_PORT = 
SMTP_SENDER_EMAIL = ""
SMTP_PASSWORD = ""
```

### Set up the cron job
* Run `crontab -e`
* Add `0,30 * * * * /bin/bash -l -c 'source invoice_emails/invoice_emails_env/bin/activate && python3 invoice_emails/send-xero-invoices/send_invoices.py' >> cron-log.txt 2>&1` to the bottom of the file, to run the script every 30 minutes