function req(first) {
    var xmlhttp = new XMLHttpRequest();
    xmlhttp.onload = function() {
        if (xmlhttp.status == 200) {
            document.querySelector("article.markdown-body").innerHTML = xmlhttp.responseText;
        } else if(xmlhttp.status == 304) {
        } else {
            console.log(xmlhttp.status, xmlhttp.statusText);
        }
        req(false);
    };
    xmlhttp.onerror = function() {
        console.log(xmlhttp.status, xmlhttp.statusText);
        setTimeout(req, 1000, false);
    };
    xmlhttp.open("GET", location.pathname + "?reload", true);
    xmlhttp.send();
}
req(true);
