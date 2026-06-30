(() => {
  const formsInScope = (scope) =>
    Array.from(
      document.querySelectorAll(
        `.action-form[data-action-scope="${CSS.escape(scope)}"]`,
      ),
    );

  const setScopeDisabled = (scope, disabled) => {
    formsInScope(scope).forEach((form) => {
      form.querySelectorAll('button[type="submit"], input[type="submit"]')
        .forEach((control) => {
          control.disabled = disabled;
          control.setAttribute("aria-disabled", String(disabled));
        });
    });
  };

  const announce = (message) => {
    const region = document.getElementById("action-announcer");
    if (region) {
      region.textContent = message;
    }
  };

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target.closest(".action-form");
      if (!form) {
        return;
      }
      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }

      const scope = form.dataset.actionScope;
      const submitter =
        event.submitter ??
        form.querySelector('button[type="submit"], input[type="submit"]');
      const busyLabel = form.dataset.busyLabel || "Working…";

      form.dataset.submitting = "true";
      form.setAttribute("aria-busy", "true");
      if (submitter) {
        submitter.dataset.idleLabel =
          submitter.textContent || submitter.value;
        if (submitter.tagName === "INPUT") {
          submitter.value = busyLabel;
        } else {
          submitter.textContent = busyLabel;
        }
      }
      if (scope) {
        setScopeDisabled(scope, true);
      }
      announce(busyLabel);
    },
    true,
  );
})();
