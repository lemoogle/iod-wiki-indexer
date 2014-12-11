iod-wiki-indexer
================

Python code to easily index a variety of Wikisites into IDOL OnDemand

For more information and for a list of all IDOL OnDemand APIs create an account on [idolondemand.com](http://idolondemand.com).

IDOL OnDemand offers many functionalities including text indexing and analytics capabilities which are the focus of this script.

Currently most MediaWiki wikis are supported. Find a list of wikis on [Wikiapiary](https://wikiapiary.com/wiki/Websites)

The core of the Wikitext extraction was modified from script by Giuseppe Attardi.
http://medialab.di.unipi.it/wiki/Wikipedia_Extractor

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

### Extra features

#### Field modification rules

Sometimes the data and the fields you get from wikipedia isn't exactly how you want it. For example the lyrics.wikia.com wiki has document titles in the format of "Artist:Song Title". We can set some regex rules in our json config to Move the Artist part out to a new "artist" field and also only keep the title of the song for the "title" field.

```json
{
"idolkey":"apikey",
"idolindex":"lyrics",
"mediawikiurl":"http://lyrics.wikia.com/",
"rules":[
  {"source":"title","pattern":"(.*?)\\:.*","output":"\\1","destination":"artist"},
  {"source":"title","pattern":".*?\\:(.*?)","output":"\\1","destination":"title"}
]
}
```

#### Categories

Wikimedia categories found in the ```[[Category:Cool]]``` format will get added to the documents indexed into the category field.

#### Template fields

Many Wikisites use templates for various informations such as infoboxes for example. This feature is barely developped but the code will attempt to extract information 

```
{Character|
name=Dude,
gender=male,
attributes=*Smart *Cool
}
```
will get added to documents as

```json

"Character_name":"[John"],
"Character_gender":["male"],
"Character_attributes":["Smart","Cool"]

```

### Future improvements

* Deal with index creation when the index does not exist.
* Deal with dump files to not redownload. Currently ``` python WikiExtractor.py --input dump.xml.gz --output extracted``` will generate lines of json for every documents
* Deal with cleanup of generated files
* allow inclusion-only , or exclusion of template names
