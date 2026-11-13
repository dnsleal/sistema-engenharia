-- O bucket "fotos" aceitava só imagens até 5 MB; passa a aceitar os documentos da medição (PDF, Word, Excel)
-- e os arquivos de referência do SINAPI (JSON), até 20 MB.
update storage.buckets set file_size_limit = 20971520, allowed_mime_types = array[
 'image/jpeg','image/png','image/webp',
 'application/pdf',
 'application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
 'application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/vnd.ms-excel.sheet.macroEnabled.12',
 'text/csv','application/json','application/octet-stream'
] where id = 'fotos';
