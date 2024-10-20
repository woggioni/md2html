function req(first) {
    const start = new Date().getTime();
    const xmlhttp = new XMLHttpRequest();
    xmlhttp.onload = function() {
        if (xmlhttp.status == 200) {
            document.querySelector("article.markdown-body").innerHTML = xmlhttp.responseText;
        } else if(xmlhttp.status == 304) {
        } else {
            console.log(xmlhttp.status, xmlhttp.statusText);
        }
        const nextCall = Math.min(1000, Math.max(0, 1000 - (new Date().getTime() - start)));
        setTimeout(req, nextCall, false);
    };
    xmlhttp.onerror = function() {
        console.log(xmlhttp.status, xmlhttp.statusText);
        setTimeout(req, 1000, false);
    };
    xmlhttp.open("GET", location.pathname + "?reload", true);
    xmlhttp.send();
}
req(true);
