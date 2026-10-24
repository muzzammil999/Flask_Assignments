const form = document.querySelector('#book-form');
const list = document.querySelector('#books');
const message = document.querySelector('#message');
const idInput = document.querySelector('#book-id');
const heading = document.querySelector('#form-heading');
const cancel = document.querySelector('#cancel');
let books = [];

function showMessage(text, kind = 'success') {
  message.textContent = text;
  message.className = `alert alert-${kind}`;
}

function resetForm() {
  form.reset(); idInput.value = ''; heading.textContent = 'Add a book'; cancel.hidden = true;
}

function renderBooks() {
  list.replaceChildren();
  if (!books.length) { list.textContent = 'No books yet.'; return; }
  for (const book of books) {
    const col = document.createElement('div');
    col.className = 'col-12';
    const card = document.createElement('div');
    card.className = 'card card-body';
    const title = document.createElement('h3');
    title.className = 'h6'; title.textContent = book.title;
    const author = document.createElement('p');
    author.textContent = `By ${book.author} · ${book.status}`;
    const edit = document.createElement('button');
    edit.className = 'btn btn-primary btn-sm me-2'; edit.textContent = 'Edit';
    edit.addEventListener('click', () => {
      idInput.value = book.id; form.elements.title.value = book.title;
      form.elements.author.value = book.author; form.elements.status.value = book.status;
      heading.textContent = 'Edit book'; cancel.hidden = false; form.elements.title.focus();
    });
    const remove = document.createElement('button');
    remove.className = 'btn btn-outline-danger btn-sm'; remove.textContent = 'Delete';
    remove.addEventListener('click', async () => {
      if (!confirm(`Delete ${book.title}?`)) return;
      try {
        const response = await fetch(`/api/books/${book.id}`, {method: 'DELETE'});
        if (!response.ok) throw new Error('Could not delete the book.');
        showMessage('Book deleted.'); resetForm(); await loadBooks();
      } catch (error) { showMessage(error.message, 'danger'); }
    });
    card.append(title, author, edit, remove); col.append(card); list.append(col);
  }
}
async function loadBooks() {
  try {
    const response = await fetch('/api/books');
    if (!response.ok) throw new Error('Could not load books.');
    books = await response.json(); renderBooks();
  } catch (error) { showMessage(error.message, 'danger'); }
}
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = {title: form.elements.title.value.trim(), author: form.elements.author.value.trim(), status: form.elements.status.value};
  const id = idInput.value;
  try {
    const response = await fetch(id ? `/api/books/${id}` : '/api/books', {
      method: id ? 'PUT' : 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) { showMessage((result.errors || [result.error]).join(' '), 'danger'); return; }
    showMessage(id ? 'Book updated.' : 'Book added.'); resetForm(); await loadBooks();
  } catch (error) { showMessage('Network error: ' + error.message, 'danger'); }
});
cancel.addEventListener('click', resetForm);
loadBooks();
