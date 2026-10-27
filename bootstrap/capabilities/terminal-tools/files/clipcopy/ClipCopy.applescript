use framework "Foundation"
use scripting additions

on open location theURL
	set encoded to current application's NSString's stringWithString:(text ((offset of ":" in theURL) + 1) thru -1 of theURL)
	set the clipboard to (encoded's stringByRemovingPercentEncoding()) as text
end open location
