async function loadEntries() {
  const res = await fetch('api.php?action=list');
  const data = await res.json();
  const list = document.getElementById('entries');
  list.textContent = '';
  for (const e of data.entries) {
    const li = document.createElement('li');
    li.textContent = e.name + ': ' + e.message;
    list.appendChild(li);
  }
}
async function addEntry(ev) {
  ev.preventDefault();
  await fetch('api.php?action=add', { method: 'POST', body: new FormData(ev.target) });
  ev.target.reset();
  loadEntries();
}
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('gb-form').addEventListener('submit', addEntry);
  loadEntries();
});
