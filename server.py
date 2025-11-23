
from __future__ import annotations
import os
import uuid
import tempfile
import zipfile
import io
from pathlib import Path
from flask import Flask, request, redirect, url_for, render_template, render_template_string, abort, jsonify, send_from_directory, send_file
from conversion.pipeline import convert_pdf_to_html, ConversionOptions

app = Flask(__name__)

# Route pour servir le HTML converti dans l'iframe
@app.route('/view/<output_id>')
def view_html(output_id):
    outputs_dir = Path('outputs')
    file_path = outputs_dir / output_id
    if not file_path.exists():
        abort(404)
    return send_file(file_path, mimetype='text/html')

# Route pour télécharger le HTML converti sous forme de ZIP
@app.route('/download/<output_id>')
def download_zip(output_id):
    outputs_dir = Path('outputs')
    file_path = outputs_dir / output_id
    if not file_path.exists():
        abort(404)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, arcname='index.html')
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=f'{output_id}.zip')



ERROR_TMPL = """
<!doctype html><html lang=fr><meta charset=utf-8><body>
<h2>Erreur</h2>
<p>{{ msg }}</p>
<p><a href="{{ url_for('index') }}">Retour</a></p>
</body></html>
"""

@app.get('/')
def index():
  return render_template('index.html')


@app.post('/convert')
def convert():
    if 'document' not in request.files:
        return jsonify(success=False, error="PDF manquant"), 400
    pdf_file = request.files['document']
    if pdf_file.filename == '':
        return jsonify(success=False, error="Nom de fichier vide"), 400

    # Sauvegarde temporaire
    work_dir = Path(tempfile.mkdtemp(prefix='dysconv_'))
    pdf_path = work_dir / pdf_file.filename
    pdf_file.save(pdf_path)

    opts = ConversionOptions(
        syllables=bool(request.form.get('syllables')),
        mute_letters=bool(request.form.get('mute_letters')),
        numbers_position=bool(request.form.get('numbers_position')),
        numbers_multicolor=bool(request.form.get('numbers_multicolor')),
    )

    try:
        html_path = convert_pdf_to_html(str(pdf_path), work_dir / 'out', opts, force=True)
        # On sauvegarde le HTML dans outputs/ avec un nom unique
        outputs_dir = Path('outputs')
        outputs_dir.mkdir(exist_ok=True)
        out_name = f"output_{uuid.uuid4().hex}_{pdf_file.filename}.html"
        out_path = outputs_dir / out_name
        html_path.replace(out_path)
        # Ajout de spacing_requested dans l'URL de prévisualisation
        spacing_requested = bool(request.form.get('spacing'))
        font_size = request.form.get('font_size', '16')
        font_family = request.form.get('font_family', 'OpenDyslexic')
        preview_url = url_for(
            'preview',
            filename=out_name,
            spacing_requested=int(spacing_requested),
            font_size=font_size,
            font_family=font_family
        )
        return jsonify(success=True, preview_url=preview_url)
    except Exception as e:
        return jsonify(success=False, error=f"Conversion échouée: {e}"), 500

# Route pour prévisualiser le HTML converti
@app.route('/preview/<filename>')
def preview(filename):
    outputs_dir = Path('outputs')
    file_path = outputs_dir / filename
    if not file_path.exists():
        abort(404)
    output_id = filename
    from flask import request as flask_request
    spacing_requested = flask_request.args.get('spacing_requested', '0') == '1'
    font_size = flask_request.args.get('font_size', '16')
    font_family = flask_request.args.get('font_family', 'OpenDyslexic')
    return render_template(
        'result.html',
        output_id=output_id,
        spacing_requested=spacing_requested,
        font_size=font_size,
        font_family=font_family
    )

if __name__ == '__main__':
    # Lancement développement
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='127.0.0.1', port=port, debug=True)
