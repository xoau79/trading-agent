# IBKR API intake checklist

Source: https://www.interactivebrokers.com/campus/traders-academy/api/
Fetch trick: interactivebrokers.com blocks automated fetching (403), but the same pages are served by the mirror domain ibkrcampus.com - swap the host, keep the path. Use the canonical interactivebrokers.com URL in each note's `source:` field.

Status: tick a box when the lesson note is written and linked in REFERENCE.md.

## Python TWS API (folder: python-tws-api/)
- [x] Course index: https://www.interactivebrokers.com/campus/trading-course/python-tws-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/what-is-the-tws-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/accessing-the-tws-python-api-source-code/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/essential-components-of-tws-api-programs/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/defining-contracts-in-the-tws-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/python-receiving-market-data/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/python-placing-orders/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/python-complex-orders/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/python-account-portfolio/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/tws-python-api-market-parameters-and-scanners/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/tws-python-api-concurrency-example/

## Client Portal API / Web API (folder: web-api/)
- [x] Course index: https://www.interactivebrokers.com/campus/trading-course/ibkrs-client-portal-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/what-is-ibkrs-client-portal-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/launching-and-authenticating-the-gateway/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/contract-search/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/requesting-market-data/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/placing-orders/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/request-modify-orders/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/complex-orders/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/account-management/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/market-scanners/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/websockets/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/financial-advisor-order-placement-management/

## Python Pandas - Donchian Channels (folder: strategy-courses/)
- [x] Course index: https://www.interactivebrokers.com/campus/trading-course/python-pandas-donchian-channels/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-pyquant-and-python-pandas/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-donchian-channel/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/implementing-donchian-channel-trading-app/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/running-the-donchian-channel/

## Excel and the TWS API (folder: excel-api/)
- [x] Course index: https://www.interactivebrokers.com/campus/trading-course/excel-and-the-tws-api/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-the-tws-excel-api-initial-setup/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/using-realtimedata-rtd-server-for-excel/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/the-dynamic-data-exchange-dde-in-excel-using-a-sample-spreadsheet/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/activex-in-excel-with-a-tws-sample-spreadsheet/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/advanced-tws-dde-functionality/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/diagnosing-issues-and-troubleshooting-with-the-tws-api/

## Trading Using R (folder: r-api/)
- [x] Course index: https://www.interactivebrokers.com/campus/trading-course/trading-using-r/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-r-and-rstudio/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/installing-r-and-rstudio/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/configuring-ibs-trader-workstation/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-ibrokers-package/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/market-data-functions/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/customizing-market-data-functions/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/order-functions/
- [x] https://www.interactivebrokers.com/campus/trading-lessons/sample-trading-strategy/

## Notes
- Course index pages do not get their own note - their content (course description, lesson order) goes into the REFERENCE.md section header. Tick them once REFERENCE.md reflects the course.
- After all boxes are ticked: do the cross-link pass (wikilinks between courses, links from existing trading notes), per the plan.
