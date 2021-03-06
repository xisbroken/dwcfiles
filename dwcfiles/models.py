import io
import magic
import secrets
import subprocess as sp
import time
from dwcfiles.utils import human_readable, retrieve_extension
from PIL import Image
from werkzeug.utils import secure_filename


HTML5_FORMATS = [
        'audio/mp4',
        'audio/mpeg',
        'audio/webm',
        'audio/ogg',
        'audio/wav',
        'audio/x-wav',
        'audio/x-pn-wav',
        'audio/flac',
        'audio/x-flac',
        'image/jpeg',
        'image/gif',
        'image/png',
        'image/svg',
        'image/bmp',
        'video/webm',
        'video/ogg',
        'video/mp4'
        ]


class UserFile:
    """Represents a file uploaded by a user
    Can be any type of file (image/sound/binary/etc.)
    Here are all its attributes saved to the MongoDB instance:

    self.title       -- The title given to a file by the user
    self.actualfile  -- The binary file provided
    self.frontpage   -- Boolean that controls if the file should be on the home page
    self.unique_id   -- A server generated ID used for its URL (e.g. /ul/<unique_id>)
    self.upload_date -- The date and time when the file has been uploaded (based on UTC/GMT)
    self.html5       -- Boolean that tells if the file can be used with HTML5 tags in the browser
    self.pinned      -- Boolean that admins can use to pin/make files permanently first
                        on the home page (not used currently)
    self.mime_type   -- The file's mime_type, guessed by the server
    self.filename    -- A filename composed of the unique_id and its original extension, used
                        for the direct link to the file (not its details page)
    """
    def __init__(self, *args, **kwargs):
        self.title = kwargs['title']
        self.actualfile = kwargs['actualfile']
        self.frontpage = kwargs['frontpage']
        self.unique_id = secrets.token_urlsafe(3)
        self.upload_date = time.strftime('%Y-%m-%dT%H:%M:%S%Z', time.gmtime())
        try:
            self.filename = self.unique_id + retrieve_extension(secure_filename(self.actualfile.filename))
        except AttributeError:
            self.filename = self.unique_id + retrieve_extension(secure_filename(kwargs['filename']))
        self.mime_type = self.get_mime_type()
        if self.mime_type in HTML5_FORMATS:
            self.html5 = True
        else:
            self.html5 = False
        self.filesize = self.get_filesize()
        self.pinned = False

    def __iter__(self):
        for key in vars(self):
            if key != 'actualfile':
                yield (key, getattr(self, key))

    def get_mime_type(self):
        """Retrieve mime type of the actual file
        """
        m = magic.from_buffer(self.actualfile.read(), mime=True)
        self.actualfile.seek(0, 0)
        return m

    @human_readable
    def get_filesize(self):
        """Retrieve file size of the actual file
        """
        self.actualfile.seek(0, 2)   # Change stream position to the end
        filesize = self.actualfile.tell()
        self.actualfile.seek(0, 0)   # Change stream position to the beginning
        return filesize

    def save_thumbnail(self, mongo_instance, video=False):
        thumb_filename = self.unique_id + '_thumb.png'
        if video:
            completed = sp.run(['ffmpeg', '-i', '-', '-ss', '00:00:01', '-vframes', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], input=self.actualfile.read(), stdout=sp.PIPE)
            f = completed.stdout
        elif not video:
            f = self.actualfile.read()
        self.actualfile.seek(0, 0)
        im = Image.open(io.BytesIO(f))
        im.thumbnail((226, 160))
        thumb = io.BytesIO()
        im.save(thumb, 'png')
        thumb.seek(0, 0)
        mongo_instance.save_file(thumb_filename, thumb)

    def save_to_db(self, mongo_instance):
        # Generate and save thumbnail if file is html5 video or image
        if self.html5:
            if 'image' in self.mime_type:
                self.save_thumbnail(mongo_instance)
            elif 'video' in self.mime_type:
                self.save_thumbnail(mongo_instance, video=True)
        # Insert metadata in userfiles database
        mongo_instance.db.userfiles.insert_one(dict(self))
        # Save actual file to GridFS
        mongo_instance.save_file(self.filename, self.actualfile)


