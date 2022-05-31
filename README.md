# news-websocket
A simple websocket that provides news headlines, SEC filings and other tweets relating to capital markets.

(Elon Musk is included in this by default given his history of causing large movements in stocks)

All messages are JSON encoded, with the field `message_type` being one of either `news`, `earnings` or `filing`.

Both `news` and `earnings` have the same fields in addition to `message_type`, being:
  * `source`: the twitter handle of the tweet author
  * `content`: the content of the tweet itself

`filing` type messages have different fields, including:
  * `type`: the type of filing, `8-K`, `10-Q` etc.
  * `ticker`: ticker of the company's traded stock 
  * `company`: the company's name
  * `url`: a direct link to the document filed


There is a version of this project being hosted at `ws://news-websocket.herokuapp.com/` that you can connect to and use freely.

