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
});
