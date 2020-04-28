$u = _.noConflict();

function splitQuery(query) {
    return query.split(/\s+/);
}

jQuery.fn.highlightText = function(text, className) {
    function highlight(node, addItems) {
        if (node.nodeType === 3) {
            var val = node.nodeValue;
            var pos = val.toLowerCase().indexOf(text);
            if (pos >= 0 &&
                !jQuery(node.parentNode).hasClass(className) &&
                !jQuery(node.parentNode).hasClass("nohighlight")) {
                var span;
                var isInSVG = jQuery(node).closest("body, svg, foreignObject").is("svg");
                if (isInSVG) {
                    span = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
                } else {
                    span = document.createElement("span");
                    span.className = className;
                }
                span.appendChild(document.createTextNode(val.substr(pos, text.length)));
                node.parentNode.insertBefore(span, node.parentNode.insertBefore(
                    document.createTextNode(val.substr(pos + text.length)),
                    node.nextSibling));
                node.nodeValue = val.substr(0, pos);
                if (isInSVG) {
                    var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                    var bbox = node.parentElement.getBBox();
                    rect.x.baseVal.value = bbox.x;
                    rect.y.baseVal.value = bbox.y;
                    rect.width.baseVal.value = bbox.width;
                    rect.height.baseVal.value = bbox.height;
                    rect.setAttribute('class', className);
                    addItems.push({
                        "parent": node.parentNode,
                        "target": rect});
                }
            }
        }
        else if (!jQuery(node).is("button, select, textarea")) {
            jQuery.each(node.childNodes, function() {
                highlight(this, addItems);
            });
        }
    }
    var addItems = [];
    var result = this.each(function() {
        highlight(this, addItems);
    });
    for (var i = 0; i < addItems.length; ++i) {
        jQuery(addItems[i].parent).before(addItems[i].target);
    }
    return result;
};

var Scorer = {
    // Implement the following function to further tweak the score for each result
    // The function takes a result array [filename, title, anchor, descr, score]
    // and returns the new score.
    /*
    score: function(result) {
      return result[4];
    },
    */

    // query matches the full name of an object
    objNameMatch: 11,
    // or matches in the last dotted part of the object name
    objPartialMatch: 6,
    // Additive scores depending on the priority of the object
    objPrio: {0:  15,   // used to be importantResults
        1:  5,   // used to be objectResults
        2: -5},  // used to be unimportantResults
    //  Used when the priority is not in the mapping.
    objPrioDefault: 0,

    // query found in title
    title: 15,
    partialTitle: 7,
    // query found in terms
    term: 5,
    partialTerm: 2
};

var Search = {
    _index : null,

    setIndex: function(index) {
        this._index = index;
    },

    performObjectSearch : function(object, otherterms) {
        var filenames = this._index.filenames;
        var docnames = this._index.docnames;
        var objects = this._index.objects;
        var objnames = this._index.objnames;
        var titles = this._index.titles;

        var i;
        var results = [];

        for (var prefix in objects) {
            for (var name in objects[prefix]) {
                var fullname = (prefix ? prefix + '.' : '') + name;
                var fullnameLower = fullname.toLowerCase()
                if (fullnameLower.indexOf(object) > -1) {
                    var score = 0;
                    var parts = fullnameLower.split('.');
                    // check for different match types: exact matches of full name or
                    // "last name" (i.e. last dotted part)
                    if (fullnameLower == object || parts[parts.length - 1] == object) {
                        score += Scorer.objNameMatch;
                        // matches in last name
                    } else if (parts[parts.length - 1].indexOf(object) > -1) {
                        score += Scorer.objPartialMatch;
                    }
                    var match = objects[prefix][name];
                    var objname = objnames[match[1]][2];
                    var title = titles[match[0]];
                    // If more than one term searched for, we require other words to be
                    // found in the name/title/description
                    if (otherterms.length > 0) {
                        var haystack = (prefix + ' ' + name + ' ' +
                            objname + ' ' + title).toLowerCase();
                        var allfound = true;
                        for (i = 0; i < otherterms.length; i++) {
                            if (haystack.indexOf(otherterms[i]) == -1) {
                                allfound = false;
                                break;
                            }
                        }
                        if (!allfound) {
                            continue;
                        }
                    }
                    var descr = objname + (', in ') + title;

                    var anchor = match[3];
                    if (anchor === '')
                        anchor = fullname;
                    else if (anchor == '-')
                        anchor = objnames[match[1]][1] + '-' + fullname;
                    // add custom score for some objects according to scorer
                    if (Scorer.objPrio.hasOwnProperty(match[2])) {
                        score += Scorer.objPrio[match[2]];
                    } else {
                        score += Scorer.objPrioDefault;
                    }
                    results.push([docnames[match[0]], fullname, '#'+anchor, descr, score, filenames[match[0]]]);
                }
            }
        }

        return results;
    },

    /**
     * search for full-text terms in the index
     */
    performTermsSearch : function(searchterms, excluded, terms, titleterms) {
        var docnames = this._index.docnames;
        var filenames = this._index.filenames;
        var titles = this._index.titles;

        var i, j, file;
        var fileMap = {};
        var scoreMap = {};
        var results = [];

        // perform the search on the required terms
        for (i = 0; i < searchterms.length; i++) {
            var word = searchterms[i];
            var files = [];
            var _o = [
                {files: terms[word], score: Scorer.term},
                {files: titleterms[word], score: Scorer.title}
            ];
            // add support for partial matches
            if (word.length > 2) {
                for (var w in terms) {
                    if (w.match(word) && !terms[word]) {
                        _o.push({files: terms[w], score: Scorer.partialTerm})
                    }
                }
                for (var w in titleterms) {
                    if (w.match(word) && !titleterms[word]) {
                        _o.push({files: titleterms[w], score: Scorer.partialTitle})
                    }
                }
            }

            // no match but word was a required one
            if ($u.every(_o, function(o){return o.files === undefined;})) {
                break;
            }
            // found search word in contents
            $u.each(_o, function(o) {
                var _files = o.files;
                if (_files === undefined)
                    return

                if (_files.length === undefined)
                    _files = [_files];
                files = files.concat(_files);

                // set score for the word in each file to Scorer.term
                for (j = 0; j < _files.length; j++) {
                    file = _files[j];
                    if (!(file in scoreMap))
                        scoreMap[file] = {};
                    scoreMap[file][word] = o.score;
                }
            });

            // create the mapping
            for (j = 0; j < files.length; j++) {
                file = files[j];
                if (file in fileMap && fileMap[file].indexOf(word) === -1)
                    fileMap[file].push(word);
                else
                    fileMap[file] = [word];
            }
        }

        // now check if the files don't contain excluded terms
        for (file in fileMap) {
            var valid = true;

            // check if all requirements are matched
            var filteredTermCount = // as search terms with length < 3 are discarded: ignore
                searchterms.filter(function(term){return term.length > 2}).length
            if (
                fileMap[file].length != searchterms.length &&
                fileMap[file].length != filteredTermCount
            ) continue;

            // ensure that none of the excluded terms is in the search result
            for (i = 0; i < excluded.length; i++) {
                if (terms[excluded[i]] == file ||
                    titleterms[excluded[i]] == file ||
                    $u.contains(terms[excluded[i]] || [], file) ||
                    $u.contains(titleterms[excluded[i]] || [], file)) {
                    valid = false;
                    break;
                }
            }

            // if we have still a valid result we can add it to the result list
            if (valid) {
                // select one (max) score for the file.
                // for better ranking, we should calculate ranking by using words statistics like basic tf-idf...
                var score = $u.max($u.map(fileMap[file], function(w){return scoreMap[file][w]}));
                results.push([docnames[file], titles[file], '', null, score, filenames[file]]);
            }
        }
        return results;
    },

    /**
     * helper function to return a node containing the
     * search summary for a given text. keywords is a list
     * of stemmed words, hlwords is the list of normal, unstemmed
     * words. the first one is used to find the occurrence, the
     * latter for highlighting it.
     */
    makeSearchSummary : function(htmlText, keywords, hlwords) {
        var text = Search.htmlToText(htmlText);
        var textLower = text.toLowerCase();
        var start = 0;
        $.each(keywords, function() {
            var i = textLower.indexOf(this.toLowerCase());
            if (i > -1)
                start = i;
        });
        start = Math.max(start - 120, 0);
        var excerpt = ((start > 0) ? '...' : '') +
            $.trim(text.substr(start, 240)) +
            ((start + 240 - text.length) ? '...' : '');
        var rv = $('<div class="context"></div>').text(excerpt);
        $.each(hlwords, function() {
            rv = rv.highlightText(this, 'highlighted');
        });
        return rv;
    },

    htmlToText : function(htmlString) {
        var htmlElement = document.createElement('span');
        htmlElement.innerHTML = htmlString;
        $(htmlElement).find('.headerlink').remove();
        docContent = $(htmlElement).find('[role=main]')[0];
        if(docContent === undefined) {
            console.warn("Content block not found. Sphinx search tries to obtain it " +
                "via '[role=main]'. Could you check your theme or template.");
            return "";
        }
        return docContent.textContent || docContent.innerText;
    },

    query: function(query) {
        this.out = $('#search-results');
        this.out.empty();
        this.output = $('<ul class="search"/>').appendTo(this.out);

        var i;

        // stem the searchterms and add them to the correct list
        var stemmer = new Stemmer();
        var searchterms = [];
        var excluded = [];
        var hlterms = [];
        var tmp = splitQuery(query);
        var objectterms = [];
        for (i = 0; i < tmp.length; i++) {
            if (tmp[i] !== "") {
                objectterms.push(tmp[i].toLowerCase());
            }

            if ($u.indexOf(stopwords, tmp[i].toLowerCase()) != -1 || tmp[i].match(/^\d+$/) ||
                tmp[i] === "") {
                // skip this "word"
                continue;
            }
            // stem the word
            var word = stemmer.stemWord(tmp[i].toLowerCase());
            // prevent stemmer from cutting word smaller than two chars
            if(word.length < 3 && tmp[i].length >= 3) {
                word = tmp[i];
            }
            var toAppend;
            // select the correct list
            if (word[0] == '-') {
                toAppend = excluded;
                word = word.substr(1);
            }
            else {
                toAppend = searchterms;
                hlterms.push(tmp[i].toLowerCase());
            }
            // only add if not already in the list
            if (!$u.contains(toAppend, word))
                toAppend.push(word);
        }
        var highlightstring = '?highlight=' + encodeURIComponent(hlterms.join(" "));

        // console.debug('SEARCH: searching for:');
        // console.info('required: ', searchterms);
        // console.info('excluded: ', excluded);

        // prepare search
        var terms = this._index.terms;
        var titleterms = this._index.titleterms;

        // array of [filename, title, anchor, descr, score]
        var results = [];
        // $('#search-progress').empty();

        // lookup as object
        for (i = 0; i < objectterms.length; i++) {
            var others = [].concat(objectterms.slice(0, i),
                objectterms.slice(i+1, objectterms.length));
            results = results.concat(this.performObjectSearch(objectterms[i], others));
        }

        // lookup as search terms in fulltext
        results = results.concat(this.performTermsSearch(searchterms, excluded, terms, titleterms));

        // let the scorer override scores with a custom scoring function
        if (Scorer.score) {
            for (i = 0; i < results.length; i++)
                results[i][4] = Scorer.score(results[i]);
        }

        // now sort the results by score (in opposite order of appearance, since the
        // display function below uses pop() to retrieve items) and then
        // alphabetically
        results.sort(function(a, b) {
            var left = a[4];
            var right = b[4];
            if (left > right) {
                return 1;
            } else if (left < right) {
                return -1;
            } else {
                // same score: sort alphabetically
                left = a[1].toLowerCase();
                right = b[1].toLowerCase();
                return (left > right) ? -1 : ((left < right) ? 1 : 0);
            }
        });

        // for debugging
        // Search.lastresults = results.slice();  // a copy
        // console.info('search results:', Search.lastresults);

        // print the results
        var resultCount = results.length;
        function displayNextItem() {
            // results left, load the summary and display it
            if (results.length) {
                var item = results.pop();
                var listItem = $('<li style="display:none"></li>');
                var requestUrl = "";
                var linkUrl = "";
                if (DOCUMENTATION_OPTIONS.BUILDER === 'dirhtml') {
                    // dirhtml builder
                    var dirname = item[0] + '/';
                    if (dirname.match(/\/index\/$/)) {
                        dirname = dirname.substring(0, dirname.length-6);
                    } else if (dirname == 'index/') {
                        dirname = '';
                    }
                    requestUrl = DOCUMENTATION_OPTIONS.URL_ROOT + dirname;
                    linkUrl = requestUrl;

                } else {
                    // normal html builders
                    requestUrl = DOCUMENTATION_OPTIONS.URL_ROOT + item[0] + DOCUMENTATION_OPTIONS.FILE_SUFFIX;
                    linkUrl = DOCUMENTATION_OPTIONS.URL_ROOT + item[0] + DOCUMENTATION_OPTIONS.LINK_SUFFIX;
                }
                listItem.append($('<a/>').attr('href',
                    linkUrl +
                    highlightstring + item[2]).html(item[1]));
                if (item[3]) {
                    listItem.append($('<span> (' + item[3] + ')</span>'));
                    Search.output.append(listItem);
                    listItem.slideDown(5, function() {
                        displayNextItem();
                    });
                } else if (DOCUMENTATION_OPTIONS.HAS_SOURCE) {
                    $.ajax({url: requestUrl,
                        dataType: "text",
                        complete: function(jqxhr, textstatus) {
                            var data = jqxhr.responseText;
                            if (data !== '' && data !== undefined) {
                                listItem.append(Search.makeSearchSummary(data, searchterms, hlterms));
                            }
                            Search.output.append(listItem);
                            listItem.slideDown(5, function() {
                                displayNextItem();
                            });
                        }});
                } else {
                    // no source available, just display title
                    Search.output.append(listItem);
                    listItem.slideDown(5, function() {
                        displayNextItem();
                    });
                }
            }
            // search finished, update title and status message
            else {
                // document.getElementById('search-results').style.display = 'block';
                // Search.stopPulse();
                // Search.title.text(('Search Results'));
                // if (!resultCount)
                //     Search.status.text(('Your search did not match any documents. Please make sure that all words are spelled correctly and that you\'ve selected enough categories.'));
                // else
                //     Search.status.text(('Search finished, found %s page(s) matching the search query.').replace('%s', resultCount));
                // Search.status.fadeIn(500);
            }
        }
        displayNextItem();
    }
};

document.addEventListener('DOMContentLoaded', function () {
    // scroll sidenav to current
    var sidenav = document.getElementById('sidenav')
    var parent = [sidenav];
    var current = parent;
    while (parent.length > 0) {
        current = parent[0];
        parent = current.getElementsByClassName('current');
    }
    sidenav.scrollTop = current.offsetTop - sidenav.clientHeight / 2;

    // language and version selector
    M.FloatingActionButton.init(document.querySelectorAll('.fixed-action-btn'), {
        hoverEnabled: false
    });

    // customize ScrollSpy
    var ScrollSpy = M.ScrollSpy, $ = window.cash;
    ScrollSpy._last = null;
    M.ScrollSpy.prototype._handleWindowScroll = function () {
        // viewport rectangle
        var top = M.getDocumentScrollTop() + this.options.scrollOffset || 200;
        var last = null;

        // determine which elements are in view
        for (var i = 0; i < ScrollSpy._elements.length; i++) {
            var scrollspy = ScrollSpy._elements[i];
            if (scrollspy.$el.height() > 0) {
                var elTop = scrollspy.$el.offset().top;
                if (top < elTop) {
                    break
                } else {
                    last = scrollspy;
                }
            }
        }
        if (last !== ScrollSpy._last) {
            if (last) {
                $(this.options.getActiveElement(last.$el.attr('id'))).addClass(this.options.activeClass);
            }
            if (ScrollSpy._last) {
                $(this.options.getActiveElement(ScrollSpy._last.$el.attr('id'))).removeClass(this.options.activeClass);
            }
            ScrollSpy._last = last;
        }
    }
    M.ScrollSpy.prototype._handleTriggerClick = function (e) {
        var $trigger = $(e.target);
        for (var i = ScrollSpy._elements.length - 1; i >= 0; i--) {
            var scrollspy = ScrollSpy._elements[i];
            if ($trigger.is('a[href="#' + scrollspy.$el.attr('id') + '"]')) {
                e.preventDefault();
                var offset = scrollspy.$el.offset().top + 1;

                M.anime({
                    targets: [document.documentElement, document.body],
                    scrollTop: offset - scrollspy.options.scrollOffset,
                    duration: 400,
                    easing: 'easeOutCubic'
                });
                history.pushState(null, null, '#' + scrollspy.$el.attr('id'));
                break;
            }
        }
    }
    var elems = document.querySelectorAll('.section .section');
    M.ScrollSpy.init(elems, {
        scrollOffset: (window.innerHeight - 64) / 5
    });

    var num = localStorage.getItem("github-star-num");
    var expire = localStorage.getItem("github-star-expire");
    if (num === null || Date.now() > parseInt(expire)) {
        fetch('https://api.github.com/repos/python-gino/gino').then(function (r) {
            r.json().then(function (resp) {
                document.getElementById('github-star-num').innerText = '' + resp.stargazers_count;
                localStorage.setItem('github-star-num', resp.stargazers_count);
                localStorage.setItem('github-star-expire', Date.now() + 3600 * 24 * 1000)
            })
        })
    } else {
        document.getElementById('github-star-num').innerText = num;
    }

    var search = document.getElementById('search');
    var sc = document.getElementById('search-container');
    var sr = document.getElementById('search-results');
    var timeoutHandle = null;
    var lastQuery = "";
    search.onkeydown = function () {
        clearTimeout(timeoutHandle);
        timeoutHandle = setTimeout(function () {
            if (search.value.trim()) {
                sr.style.display = 'block';
                if (search.value !== lastQuery) {
                    Search.query(search.value);
                    lastQuery = search.value;
                }
            } else {
                sr.innerHTML = "";
                sr.style.display = 'none';
                lastQuery = "";
            }
        }, 250);
    }
    search.onfocus = function () {
        if (sr.innerHTML)
            sr.style.display = 'block';
    }
    var scrollOffset = 64 + (window.innerHeight - 64) / 5;
    var anchors = document.querySelectorAll(
        'dt[id]:not([id=""]), a.footnote-reference, span[id]:not([id=""])');
    window.addEventListener('click', function (e) {
        if (!sc.contains(e.target)) {
            sr.style.display = 'none';
        }

        var $trigger = $(e.target);
        while ($trigger.length > 0 && !$trigger.is('a')) {
            $trigger = $trigger.parent()
        }
        for (var i = anchors.length - 1; i >= 0; i--) {
            var target = anchors[i];
            if ($trigger.is('a[href="#' + target.getAttribute('id') + '"]')) {
                e.preventDefault();
                var offset = target.offsetTop + 1;

                M.anime({
                    targets: [document.documentElement, document.body],
                    scrollTop: offset - scrollOffset,
                    duration: 400,
                    easing: 'easeOutCubic'
                });
                history.pushState(null, null, '#' + target.getAttribute('id'));
                break;
            }
        }
    });
    setTimeout(function () {
        var hash = location.hash.substring(1);
        if (!hash) return;
        var target = $('[id="' + hash + '"]');
        if (target.length === 0) return;
        if (parseInt(target.offset().top) !== parseInt(document.documentElement.scrollTop))
            return;

        document.documentElement.scrollTop -= 64
    }, 100);
    jQuery('.boxed-nav li').each(function (i, li) {
        jQuery(li).wrapInner('<a href="' + jQuery('a:first', li).attr('href') + '"><div></div></a>');
    });
});
