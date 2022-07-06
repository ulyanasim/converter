import os
import argparse
import glog as log
from lxml import etree
import requests
import re

def parse_args():
    """Parse arguments of command line"""
    parser = argparse.ArgumentParser(
        description='Convert CVAT XML annotations to YOLO format'
    )

    parser.add_argument(
        '--cvat-xml', metavar='FILE', required=True,
        help='input file with CVAT annotation in xml format'
    )

    parser.add_argument(
        '--image-dir', metavar='DIRECTORY', required=False,
        help='directory which contains original images'
    )

    parser.add_argument(
        '--output-dir', metavar='DIRECTORY', required=True,
        help='directory for output annotations in YOLO format'
    )

    parser.add_argument(
        '--username', metavar='USERNAME', required=False,
        help='Username from CVAT Login page, required to download images'
    )

    parser.add_argument(
        '--password', metavar='PASSWORD', required=False,
        help='Password from CVAT Login page, required to download images'
    )

    parser.add_argument(
        '--labels', metavar='ILABELS', required=False,
        help='Labels (separated by comma) to extract. Example: car,truck,motorcycle'
    )

    return parser.parse_args()


def process_cvat_xml(xml_file, image_dir, output_dir,username,password,ilabels):
    """
    Transforms a single XML in CVAT format to YOLO TXT files and download images when not in IMAGE_DIR
    :param xml_file: CVAT format XML
    :param image_dir: image directory of the dataset
    :param output_dir: directory of annotations with YOLO format
    :param username: Username used to login CVAT. Required to download images
    :param password: Password used to login CVAT. Required to download images
    :param ilabels: Comma separated ordered labels
    :return:
    """
    KNOWN_TAGS = {'polygon', 'image', 'attribute'}

    if (image_dir is None):
        image_dir=os.path.join(output_dir,"content/rosneft/parts/1")
        os.makedirs(image_dir, exist_ok=True)

    os.makedirs(output_dir, exist_ok=True)
    cvat_xml = etree.parse(xml_file)
    basename = os.path.splitext( os.path.basename( xml_file ) )[0]
    current_labels = {}
    traintxt = ""
    auto_lbl_count = 0

    if (ilabels is not None):
        vlabels=ilabels.split(',')
        for _label in vlabels:
            current_labels[_label]=auto_lbl_count
            auto_lbl_count+=1

    tracks= cvat_xml.findall( './/track' )

    if (tracks is not None) and (len(tracks) > 0):
        frames = {}

        for track in tracks:
            trackid = int(track.get("id"))
            label = track.get("label")
            polygons = track.findall( './polygon' )
            for polygon in polygons:
                frameid  = int(polygon.get('frame'))
                outside  = int(polygon.get('outside'))
                occluded = int(polygon.get('occluded'))
                points_1 = str(polygon.get('points'))
                points = points_1.replace(";", " ")
                x0      = float(points[1])
                y0     = float(points[2])
                x1      = float(points[3])
                y1     = float(points[4])
                x2      = float(points[5])
                y2     = float(points[6])
                x3      = float(points[7])
                y3     = float(points[8])
                x4      = float(points[9])
                y4     = float(points[10])

                frame = frames.get( frameid, {} )

                if outside == 0:
                    frame[ trackid ] = { 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,'x2': x2, 'y2': y2, 'x3': x3, 'y3': y3, 'x4': x4, 'y4': y4, 'label': label }

                frames[ frameid ] = frame

        width = int(cvat_xml.find('.//original_size/width').text)
        height  = int(cvat_xml.find('.//original_size/height').text)

        taskid = int(cvat_xml.find('.//task/id').text)

        urlsegment = cvat_xml.find(".//segments/segment/url").text
        urlbase = urlsegment.split("?")[0]

        httpclient = requests.session()
        httpclient.get(urlbase)

        csrftoken = "none"
        sessionid = "none"

        for frameid in sorted(frames.keys()):
            image_name = "%DSC_%s.jpg" % (basename, frameid)
            image_path = os.path.join(image_dir, image_name)
            if not os.path.exists(image_path):
                if username is None:
                    log.warn('{} image cannot be found. Is `{}` image directory correct?\n'.format(image_path, image_dir))
                else:
                    log.info('{} image cannot be found. Downloading from task ID {}\n'.format(image_path, taskid))

                    if sessionid == "none":
                        if "csrftoken" in httpclient.cookies:
                            csrftoken = httpclient.cookies["csrftoken"]
                        elif "csrf" in httpclient.cookies:
                            csrftoken = httpclient.cookies["csrf"]

                        login_data = dict(username=username, password=password,
                                        csrfmiddlewaretoken=csrftoken, next='/dashboard')

                        urllogin = urlbase+"/auth/login"
                        httpclient.post(urllogin, data=login_data,
                                        headers=dict(Referer=urllogin))

                        if ("sessionid" in httpclient.cookies):
                            sessionid = httpclient.cookies["sessionid"]

                    url = urlbase+"/api/v1/tasks/"+str(taskid)+"/frames/"+ str(frameid)

                    req = httpclient.get(url, headers=dict(
                        csrftoken=csrftoken, sessionid=sessionid))

                    with open(image_path, 'wb') as fo:
                        fo.write(req.content)
                        print('Url saved as %s\n' % image_path)


            frame = frames[frameid]

            _yoloAnnotationContent=""

            objids = sorted(frame.keys())

            for objid in objids:

                polygon = frame[objid]
                label = polygon.get('label')
                points_1 = str(polygon.get('points'))
                points = points_1.replace(";", " ") 
                x0      = float(points[1])
                y0     = float(points[2])
                x1      = float(points[3])
                y1     = float(points[4])
                x2      = float(points[5])
                y2     = float(points[6])
                x3      = float(points[7])
                y3     = float(points[8])
                x4      = float(points[9])
                y4     = float(points[10])
                x = [x0, x1, x2, x3, x4]
                y = [y0, y1, y2, y3, y4]
                xmax = max(x)
                xmin = min(x)
                ymax = max(y)
                ymin = min(y)
                if not label in current_labels:
                    current_labels[label] = auto_lbl_count
                    auto_lbl_count+=1

                labelid=current_labels[label]
                yolo_x= (xmin + ((xmax-xmin)/2))/width
                yolo_y= (ymin + ((ymax-ymin)/2))/height
                yolo_w = (xmax - xmin) / width
                yolo_h = (ymax - ymin) / height

                if len(_yoloAnnotationContent) != 0:
                        _yoloAnnotationContent += "\n"

                _yoloAnnotationContent+=str(labelid)+" "+"{:.6f}".format(yolo_x) +" "+"{:.6f}".format(yolo_y) +" "+"{:.6f}".format(yolo_w) +" "+"{:.6f}".format(yolo_h)
            anno_name = os.path.basename(os.path.splitext(image_name)[0] + '.txt')
            anno_path = os.path.join(image_dir, anno_name)

            _yoloFile = open(anno_path, "w", newline="\n")
            _yoloFile.write(_yoloAnnotationContent)
            _yoloFile.close()

            if len(traintxt)!=0:
                traintxt+="\n"

            traintxt+=image_path

    else:
        for img_tag in cvat_xml.findall('image'):
            image_name = img_tag.get('name')
            width = img_tag.get('width')
            height = img_tag.get('height')
            image_path = os.path.join(image_dir, image_name)
            if not os.path.exists(image_path):
                log.warn('{} image cannot be found. Is `{}` image directory correct?'.
                    format(image_path, image_dir))

            unknown_tags = {x.tag for x in img_tag.iter()}.difference(KNOWN_TAGS)
            if unknown_tags:
                log.warn('Ignoring tags for image {}: {}'.format(image_path, unknown_tags))

            _yoloAnnotationContent = ""

            for polygon in img_tag.findall('polygon'):
                label = polygon.get('label')
                points_1 = str(polygon.get('points'))
                points = points_1.replace(";", " ")
                x0      = float(points[1])
                y0     = float(points[2])
                x1      = float(points[3])
                y1     = float(points[4])
                x2      = float(points[5])
                y2     = float(points[6])
                x3      = float(points[7])
                y3     = float(points[8])
                x4      = float(points[9])
                y4     = float(points[10])
                x = [x0, x1, x2, x3, x4]
                y = [y0, y1, y2, y3, y4]
                xmax = max(x)
                xmin = min(x)
                ymax = max(y)
                ymin = min(y)

                if not label in current_labels:
                    current_labels[label] = auto_lbl_count
                    auto_lbl_count += 1

                labelid = current_labels[label]
                yolo_x = (xmin + ((xmax-xmin)/2))/width
                yolo_y = (ymin + ((ymax-ymin)/2))/height
                yolo_w = (xmax - xmin) / width
                yolo_h = (ymax - ymin) / height

                if len(_yoloAnnotationContent) != 0:
                        _yoloAnnotationContent += "\n"

                _yoloAnnotationContent += str(labelid)+" "+"{:.6f}".format(yolo_x) + " "+"{:.6f}".format(
                    yolo_y) + " "+"{:.6f}".format(yolo_w) + " "+"{:.6f}".format(yolo_h)

            anno_name = os.path.basename(os.path.splitext(image_name)[0] + '.txt')
            anno_path = os.path.join(image_dir, anno_name)

            _yoloFile = open(anno_path, "w", newline="\n")
            _yoloFile.write(_yoloAnnotationContent)
            _yoloFile.close()

    traintxt_file=open(output_dir+"/train.txt","w",newline="\n")
    traintxt_file.write(traintxt)
    traintxt_file.close()


def main():
    args = parse_args()
    process_cvat_xml(args.cvat_xml, args.image_dir, args.output_dir, args.username,args.password,args.labels)


if __name__ == "__main__":
    main()
