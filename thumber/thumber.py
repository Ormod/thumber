"""Thumber Library
Author Hannu Valtonen"""
from cStringIO import StringIO
import json
import re
import struct
import sys
import Image

INDEX_VERSION = 2
MAX_PIXELS = 100 * 1024 * 1024 # 100 megapixels
MAX_DIMENSION = 15000 # max dimension

class ThumberError(Exception):
    """Thumber error"""

class Thumber(object):
    """Thumber librarys main class, use this if you want to use everything"""
    def __init__(self, thumbnail_sizes = None, file_types = None):
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

        self.thumb_indexer = ThumberIndex()

    def create_thumbs_and_index(self, file_path = None, data_blob = None, extra_data = None, quality = 75):
        """Create thumbnails and an index, and add possible additional keys to the file index"""
        if data_blob:
            input_data = StringIO(data_blob)
        else:
            input_data = file_path

        result_dict = self.create_thumbnails(input_data, quality)
        return self.thumb_indexer.create_thumbnail_blob_with_index(result_dict, extra_data)

    def create_thumbnails(self, input_data, quality = 75):
        """Create required thumbnails, sizes are set in object instance creation time"""
        # Try to load the image w/ PIL
        try:
            orig_image = Image.open(input_data)
        except:
            raise ThumberError("Could not open image with PIL")

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

                if file_type == 'jpeg':
                    image.save(file_buffer, format = file_type, quality = quality)
                else:
                    image.save(file_buffer, format = file_type)
                index_file_type = file_type if file_type != "jpeg" else "jpg"
                key = "DATA.%sx%sx%s" % (thumbnail_size[0], thumbnail_size[1], index_file_type)
                result_dict[key] = file_buffer.getvalue()
                real_size_key = "r%sx%s" % (thumbnail_size[0], thumbnail_size[1])
                real_size_value = "%sx%s" % (image.size[0], image.size[1])
                result_dict[real_size_key] = real_size_value

        return result_dict

class ThumberIndex(object):
    """Class for creating files with n thumbnails and an access index"""
    def create_thumbnail_blob_with_index(self, results, extra_data):
        """Expects a dict like {'128x128xjpg': thumbnail_data, '64x64xjpg': thumbnail2_data, 'my_reserved_key': 1}"""
        header, blobs = {}, []
        header_alloc = len(results) * (16 * 3)

        if extra_data:
            results = dict(results.items() + extra_data.items())
            header_alloc += len(json.dumps(extra_data))
        else:
            extra_data = {}

        offset = header_alloc
        for k, v in results.iteritems():
            if k.startswith("DATA."):
                # Store offsets in "start-end" byte ranges from beginning of the file
                k = k[5:]
                begin = offset
                end = offset + len(v)
                offset = end
                blobs.append(v)
                header[k] = "%d-%d" % (begin, end)
            else:
                # Something else, store as-is
                header[k] = v

        json_header = json.dumps(header)
        padding = header_alloc - len(json_header) - 4
        assert padding >= 0, "Header allocation %r < data size %r" % (header_alloc, len(json_header))
        data = [struct.pack("HH", INDEX_VERSION, len(json_header)), json_header, padding * "\x00"] + blobs
        return ''.join(data), header

    def read_thumbnail_blob_with_index(self, data_blob, thumbnail_key = None):
        """Expects a data blob created by create_thumbnail_file_with_index
        If thumbnail_key has been given, returns the blob in question
        otherwise return a thumbnail_dict with all available thumbnail sizes
        """
        index_version, header_length = struct.unpack("HH", data_blob[:4])
        header = json.loads(data_blob[4:4 + header_length])
        total_header_length = header_length + 4

        def get_offsets(offsets):
            if index_version == 2:
                start_offset, _, end_offset = offsets.partition("-")
            elif index_version == 1:
                start_offset = offsets[0] + total_header_length
                end_offset = offsets[1] + total_header_length
            return int(start_offset), int(end_offset)

        if thumbnail_key:
            start_offset, end_offset = get_offsets(header[thumbnail_key])
            return data_blob[start_offset:end_offset]

        return_dict = {}
        pat = re.compile("^[0-9]+x[0-9]+x[a-z]+$")
        for k, v in header.iteritems():
            if pat.match(k):
                start_offset, end_offset = get_offsets(v)
                return_dict[k] = data_blob[start_offset:end_offset]
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
        data_blob, header = a.create_thumbs_and_index(file_path = sys.argv[2])
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
