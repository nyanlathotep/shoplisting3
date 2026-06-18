function confirmModal({ 
    modalId, 
    title = "Confirm", 
    body = "Are you sure?", 
    onConfirm = () => {} 
}) {
    const $modal = $(modalId);
    const $title = $modal.find('.modal-title');
    const $body = $modal.find('.modal-body');
    const $confirmBtn = $modal.find('.confirm-btn');

    // Set content
    $title.text(title);
    $body.text(body);

    // Remove any previous click handlers
    $confirmBtn.off('click');

    // Add the new one
    $confirmBtn.on('click', function() {
        $modal.modal('hide');
        onConfirm();
    });

    // Show modal
    $modal.modal('show');
}
