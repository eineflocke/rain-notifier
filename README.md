# rain-notifier

sends email when rain approaches

relys on resources on Japan Meteorological Agency (JMA) website
https://www.jma.go.jp/bosai/nowc/

## usage

1. change email settings in `rain-notifier.py` (3 lines) to your own

```py
msg['From'] = 'from@example.com'
msg['To'] = 'to@example.com'
server = SMTP('example.com', 25)
```

2. execute directly with your lat & lon or cron it every 5 minutes

```sh
./rain-notifier.py 35.681 139.767
02-57/5 * * * * /path/to/rain-notifier.py 35.681 139.767 > /path/to/log 2>&1
```
