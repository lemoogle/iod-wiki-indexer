iod-wiki-indexer
================

Python code to easily index a variety of Wikisites into IDOL OnDemand

For more information and for a list of all IDOL OnDemand APIs create an account on [idolondemand.com](http://idolondemand.com).

IDOL OnDemand offers many functionalities including text indexing and analytics capabilities which are the focus of this script.

Currently most MediaWiki wikis are supported. Find a list of wikis on [Wikiapiary](https://wikiapiary.com/wiki/Websites)

###Install


Just run a pip install to install the dependecies ( currently only one )

```bash
pip install -r requirements.txt
```

###Usage

Create an index on IDOL Ondemand.com either using the [Create Text Index API](https://www.idolondemand.com/developer/apis/createtextindex#overview) or through the [Dashboard](https://www.idolondemand.com/account/text-indexes.html) ( need to be logged , Account -> Tools -> Manage Text Indexes)

Create a json file ```starwars.json``` 

```json
{
"idolkey":"yourapikeyhere",
"idolindex":"starwarsindex",
"mediawikiurl":"http://starwars.wikia.com/"
}
```

And then run the script 

```bash
python WikiExtractor.py --config starwars.json
```

In many cases, when dealing with a Wikia page , the script will attempt to download a Database Dump from the
[Wikia statistics page](http://starwars.wikia.com/wiki/Special:Statistics).

In other cases like a gamepedia wiki it will resort to using the wikimedia API. 

```json
{
"idolkey":"youapikey",
"idolindex":"awesomenautsgamepedia",
"mediawikiurl":"http://awesomenauts.gamepedia.com/"
}
```


### Future improvements

* Deal with index creation when the index does not exist.
* Deal with dump files to not redownload. Currently ``` python WikiExtractor.py --input dump.xml.gz --output extracted``` will generate lines of json for every documents
* Deal with cleanup of generated files
