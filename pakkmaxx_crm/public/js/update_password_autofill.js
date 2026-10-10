// Pakkmaxx: Frappe's /update-password page (used when an invited user creates their password) enables its
// "Confirm" button only on keyup/paste. A password filled by the browser, the phone's "strong password"
// suggestion or a password manager fires input/change but no key events, so the button stayed disabled and
// the invitee could not finish. Re-run the page's own check for those events too.
(function () {
	if (window.location.pathname !== "/update-password") return;
	var ids = ["old_password", "new_password", "confirm_password"];

	function recheck(el) {
		if (window.jQuery) window.jQuery(el).trigger("keyup");
	}

	function relay(event) {
		var el = event.target;
		if (el && ids.indexOf(el.id) !== -1) recheck(el);
	}

	document.addEventListener("input", relay, true);
	document.addEventListener("change", relay, true);

	// Fields can be autofilled before this runs (or without any event): check once the page is ready.
	window.addEventListener("load", function () {
		setTimeout(function () {
			var el = document.getElementById("confirm_password");
			if (el && el.value) recheck(el);
		}, 600);
	});
})();
