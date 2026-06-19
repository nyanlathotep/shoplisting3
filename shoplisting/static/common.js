function confirm_modal({ 
    modalId,
    title = "Confirm",
    body = "Are you sure?",
    confirmText = "Delete",
    confirmCls = "btn btn-danger",
    onConfirm = () => {}
}) {
    const $modal = $(modalId);
    const $title = $modal.find('.modal-title');
    const $body = $modal.find('.modal-body');
    const $confirmBtn = $modal.find('.confirm-btn');

    // Set content
    $title.text(title);
    $body.text(body);
    $confirmBtn.text(confirmText);
    $confirmBtn.attr('class', 'confirm-btn');
    $confirmBtn.addClass(confirmCls);

    // Remove any previous click handlers
    $confirmBtn.off('click.slmodal');

    // Add the new one
    $confirmBtn.on('click.slmodal', function() {
        $modal.modal('hide');
        onConfirm();
    });

    // Show modal
    $modal.modal('show');
}

function flashError(message) {
    const container = $('.container, .card-body').first();

    // Remove older alerts if more than 3 exist
    const alerts = container.find('.alert-danger');
    if (alerts.length >= 3) {
        // remove the oldest (last one)
        alerts.last().remove();
    }

    const alert = $(`
        <div class="alert alert-danger alert-dismissible fade show mt-3" role="alert">
            ${message}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        </div>
    `);

    container.prepend(alert);

    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}
