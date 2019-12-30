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
                    if (last !== ScrollSpy._last) {
                        if (last) {
                            $(this.options.getActiveElement(last.$el.attr('id'))).addClass(this.options.activeClass);
                        }
                        if (ScrollSpy._last) {
                            $(this.options.getActiveElement(ScrollSpy._last.$el.attr('id'))).removeClass(this.options.activeClass);
                        }
                        ScrollSpy._last = last;
                        if (last) {
                            console.log(last.$el);
                        }
                    }
                    break
                } else {
                    last = scrollspy;
                }
            }
        }
    }

    var elems = document.querySelectorAll('.section .section');
    M.ScrollSpy.init(elems, {
        scrollOffset: (window.innerHeight - 64) / 5
    });
});
