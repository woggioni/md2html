
function req(first, previousETag) {
    const minInterval = 2000;
    const start = new Date().getTime();
    const xmlhttp = new XMLHttpRequest();
    xmlhttp.onload = function() {
        const eTag = xmlhttp.getResponseHeader("Etag")
        if (xmlhttp.status == 200 && eTag !== previousETag) {
            document.querySelector("article.markdown-body").innerHTML = xmlhttp.responseText;
        }
        const nextCall = Math.min(minInterval, Math.max(0, minInterval - (new Date().getTime() - start)));
        setTimeout(req, nextCall, false, eTag);
    };
    xmlhttp.onerror = function() {
        console.log(xmlhttp.status, xmlhttp.statusText);
        setTimeout(req, minInterval, false, previousETag);
    };
    xmlhttp.open("GET", location.pathname + "?reload", true);
    xmlhttp.send();
}
req(true, null);
