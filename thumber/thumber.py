"""Thumber Library
Author Hannu Valtonen"""
import struct
import sys
from cStringIO import StringIO

import Image

try:
    import json
except ImportError:
    import simplejson as json

try:
    import pyffmpeg
except ImportError:
    # pyffmpeg packaging is slightly broken, try to work around it.
    from distutils.sysconfig import get_python_lib
    sys.path.insert(-1, get_python_lib())
    try:
        import pyffmpeg
    except ImportError:
        pyffmpeg = None

INDEX_VERSION = 1
MAX_PIXELS = 100 * 1024 * 1024 # 100 megapixels
MAX_DIMENSION = 15000 # max dimension

class ThumberError(Exception):
    """Thumber error"""

class Thumber(object):
    """Thumber librarys main class, use this if you want to use everything"""
    def __init__(self, thumbnail_sizes = None, reserved_keys = None, file_types = None):
        if thumbnail_sizes:
            self.thumbnail_sizes = thumbnail_sizes
        else:
            self.thumbnail_sizes = ((128, 128), (64, 64), (32, 32)) #default sizes
        if file_types:
            self.file_types = []
            for file_type in file_types:
                if file_type == "jpg":
                    self.file_types.append("jpeg")
                else:
                    self.file_types.append(file_type)
        else:
            self.file_types = ['jpeg', 'gif', 'png']

        self.thumb_indexer = ThumberIndex(reserved_keys)

    def create_thumbs_and_index(self, file_path = None, data_blob = None, extra_keys_dict = None):
        """Create thumbnails and an index, and add possible additional keys to the file index"""
        if data_blob:
            input_data = StringIO(data_blob)
        else:
            input_data = file_path

        result_dict = self.create_thumbnails(input_data)
        return self.thumb_indexer.create_thumbnail_blob_with_index(result_dict, extra_keys_dict = extra_keys_dict)

    def create_thumbnails(self, input_data):
        """Create required thumbnails, sizes are set in object instance creation time"""
        # Try to load the image w/ PIL and PyFFMPEG
        try:
            orig_image = Image.open(input_data)
        except:
            if not pyffmpeg:
                raise ThumberError("Could not open image with PIL")
            try:
                s = pyffmpeg.VideoStream()
                s.open(input_data)
                orig_image = s.GetFrameNo(0)
            except:
                raise ThumberError("Could not open image with PIL or PyFFMPEG")

        # Don't even try to resize too big images
        if orig_image.size[0] > MAX_DIMENSION or orig_image.size[1] > MAX_DIMENSION:
            raise ThumberError("Image too large, maximum dimension %r, image size %r" % \
                (MAX_DIMENSION, orig_image.size))
        if orig_image.size[0] * orig_image.size[1] > MAX_PIXELS:
            raise ThumberError("Image too large, maximum pixles %r, image size %r" % \
                (MAX_PIXELS, orig_image.size))

        # Check EXIF tags for orientation.  The tag in question is 0x0112
        orientation = 0
        try:
            tags = orig_image._getexif()
            orientation = tags[0x0112]
        except:
            pass # ignore errors.

        # Rotate if needed (orientation: 1 means that no rotation is needed)
        if orientation == 2:
            orig_image = orig_image.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            orig_image = orig_image.transpose(Image.ROTATE_180)
        elif orientation == 4:
            orig_image = orig_image.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            orig_image = orig_image.transpose(Image.FLIP_TOP_BOTTOM)
            orig_image = orig_image.transpose(Image.ROTATE_270)
        elif orientation == 6:
            orig_image = orig_image.transpose(Image.ROTATE_270)
        elif orientation == 7:
            orig_image = orig_image.transpose(Image.FLIP_LEFT_RIGHT)
            orig_image = orig_image.transpose(Image.ROTATE_270)
        elif orientation == 8:
            orig_image = orig_image.transpose(Image.ROTATE_90)

        result_dict = {}
        for file_type in self.file_types:
            for thumbnail_size in self.thumbnail_sizes:
                image = orig_image.copy()
                if image.size[0] <= thumbnail_size[0] and image.size[1] <= thumbnail_size[1]:
                    image.thumbnail((image.size[0], image.size[1]), Image.ANTIALIAS)
                else:
                    image.thumbnail(thumbnail_size, Image.ANTIALIAS)
                file_buffer = StringIO()
                if image.mode != "RGB":
                    image = image.convert("RGB")

                image.save(file_buffer, format = file_type)
                index_file_type = file_type if file_type != "jpeg" else "jpg"
                key = "%sx%sx%s" % (thumbnail_size[0], thumbnail_size[1], index_file_type)
                result_dict[key] = file_buffer.getvalue()

        return result_dict

class ThumberIndex(object):
    """Class for creating files with n thumbnails and an access index"""
    def __init__(self, reserved_keys = None):
        self.reserved_keys = reserved_keys or []

    def create_thumbnail_blob_with_index(self, result_dict, extra_keys_dict = None):
        """Expects a dict like {'128x128xjpg': thumbnail_data, '64x64xjpg': thumbnail2_data, 'my_reserved_key': 1}"""
        header, data, current_offset = {}, [], 0
        if extra_keys_dict:
            result_dict.update(extra_keys_dict)
        else:
            extra_keys_dict = {}

        for k, v in result_dict.iteritems():
            if k not in self.reserved_keys + extra_keys_dict.keys():
                offsets = [current_offset, current_offset + len(v)]
                header[k] = offsets
                current_offset += len(v)
                data.append(v)
            else:
                header[k] = v
        json_header = json.dumps(header)
        data_list = [struct.pack("HH", INDEX_VERSION, len(json_header)), json_header]
        data_list.extend(data)
        return ''.join(data_list)

    def read_thumbnail_blob_with_index(self, data_blob, thumbnail_key = None, extra_reserved_keys = None):
        """Expects a data blob created by create_thumbnail_file_with_index
        If thumbnail_key has been given, returns the blob in question
        otherwise return a thumbnail_dict with all available thumbnail sizes
        """
        if not extra_reserved_keys:
            extra_reserved_keys = []

        index_version, header_length = struct.unpack("HH", data_blob[:4])
        header = json.loads(data_blob[4:4 + header_length])
        total_header_length = header_length + 4

        if thumbnail_key:
            start_offset, stop_offset = header[thumbnail_key]
            return data_blob[total_header_length + start_offset:total_header_length + stop_offset]

        return_dict = {}
        for k, v in header.iteritems():
            if k not in self.reserved_keys + extra_reserved_keys:
                return_dict[k] = data_blob[total_header_length + v[0]:total_header_length + v[1]]
            else:
                return_dict[k] = v
        return return_dict

def help_msg():
    """Help msg function for thumber"""
    print "Help:"
    print "    thumber store <input_image_file> <output_thumbnail_index_file>"
    print "    thumber load <input_thumbnail_index> <size> <output_thumbnail_image.jpg>"
    print "Thumber Copyright Hannu Valtonen 2011"

def main():
    """Entry point for thumber console script"""
    if len(sys.argv) < 4:
        help_msg()
        sys.exit(1)
    a = Thumber()
    if sys.argv[1] == "store":
        data_blob = a.create_thumbs_and_index(file_path = sys.argv[2])
        output_filename = sys.argv[3]
    elif sys.argv[1] == "load" and len(sys.argv) == 5:
        input_data = file(sys.argv[2], "rb").read()
        data_blob = a.thumb_indexer.read_thumbnail_blob_with_index(input_data, sys.argv[3])
        output_filename = sys.argv[4]
    else:
        help_msg()
        sys.exit(1)
    output_file = file(output_filename, "wb")
    output_file.write(data_blob)
    output_file.close()

if __name__ == "__main__":
    main()
