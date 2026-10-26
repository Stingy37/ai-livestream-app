// [RJ] for TY_WARN.html
// Update: 2026-10-23 02:28:00
var DataPath = 'typhoon/TY_WARN/';
var File_Time = '202610221800';
var PTA_InitTime = '202610221800';

var TY29_TabBody_C = ''+
    '<div class="col-md-6">'+
        '<h3>中度颱風 薔琵（國際命名 CHAMPI ）海上陸上颱風警報</h3>'+
        '<span class="gray-bar">編號第29號颱風警報 第10報</span>'+
        '<p>發布時間：10/23 02:30</p>'+
        '<img src="/Data/typhoon/TY_WARN/B20.png?T='+File_Time+'" alt="颱風動態圖" class="img-responsive margin-top-30">'+
    '</div>'+
    '<div class="col-md-6">'+
        '<div class="col-md-12 margin-bottom-10 WPPS_DIV"></div>'+
        '<h4 class="title-blu">颱風現況</h4>'+
        '<ul class="list-unstyled typ-nowlist">'+
            '<li><span>中心位置：</span><span>23日2時的中心位置在北緯 21.8 度，東經 124.3 度，即在鵝鑾鼻的東方約 360 公里之處</span></li>'+
            '<li><span>前進方向：</span><span>以每小時24轉8公里速度，向北北西進行</span></li>'+
            '<li><span>中心氣壓：</span><span>945百帕</span></li>'+
            '<li><span>近中心最大風速：</span><span>近中心最大風速每秒 43 公尺（約每小時 155 公里），相當於 14 級風</span></li>'+
            '<li><span>瞬間之最大陣風：</span><span>瞬間最大陣風每秒 53 公尺（約每小時 191 公里），相當於 16 級風</span></li>'+
            '<li><span>暴風半徑：</span><span>七級風平均暴風半徑320公里<br>(西北側350公里、東北側350公里、<br>西南側290公里、東南側300公里)，<br>十級風平均暴風半徑140公里<br>(西北側140公里、東北側140公里、<br>西南側140公里、東南側140公里)</span></li>'+
        '</ul>'+
        '<h4 class="title-blu">颱風預測</h4>'+
        '<p>預測24日2時的中心位置在北緯 24.9 度，東經 122.5 度，即在宜蘭的東北東方約 80 公里之處</p>'+
    '</div>';
var TY29_TabBody_E = ''+
    '<div class="col-md-6">'+
        '<h3>TYPHOON CHAMPI<br>Sea and Land Typhoon Warning</h3>'+
        '<span class="gray-bar">Report No. 10 of Typhoon No. 202629</span>'+
        '<p>Issued: 10/23 02:30</p>'+
        '<img src="/Data/typhoon/TY_WARN/B20eng.png?T='+File_Time+'" alt="Path graph" class="img-responsive margin-top-30">'+
    '</div>'+
    '<div class="col-md-6">'+
        '<div class="col-md-12 margin-bottom-10 WPPS_DIV"></div>'+
        '<h4 class="title-blu">Analysis</h4>'+
        '<ul class="list-unstyled typ-nowlist">'+
            '<li><span>Center Location: </span><span>Position 221800Z at 21.8N 124.3E</span></li>'+
            '<li><span>Movement: </span><span>Movement next 24hrs NNW 24 km/hr becoming 8 km/hr</span></li>'+
            '<li><span>Min Surface Pressure: </span><span>945 hPa</span></li>'+
            '<li><span>Max Sustained Winds Near Center: </span><span>Max sustained winds near center 43 meter per second</span></li>'+
            '<li><span>Gusts: </span><span>Gusts 53 meter per second</span></li>'+
            '<li><span>Radius: </span><span>Average radius of over 15m/s winds 320km<br>(350km NW quad. , <br class="hidden visible-xs">350km NE quad. , <br>290km SW quad. , <br class="hidden visible-xs">300km SE quad. ), <br>Average radius of over 25m/s winds 140km<br>(140km NW quad. , <br class="hidden visible-xs">140km NE quad. , <br>140km SW quad. , <br class="hidden visible-xs">140km SE quad. )</span></li>'+
        '</ul>'+
        '<h4 class="title-blu">Forecast</h4>'+
        '<p>Position 231800Z at 24.9N 122.5E</p>'+
    '</div>';
var TY_WARN_LIST = {
	'C':[
		{'ID':'TY29','TabName':'中度颱風 薔琵','TabBody':TY29_TabBody_C}
	],
	'E':[
		{'ID':'TY29','TabName':'TYPHOON CHAMPI','TabBody':TY29_TabBody_E}
	]
};

var WPPS_BTN = {'C':'','E':''};

WPPS_BTN['C'] = ''+
            '<div class="col-sm-6">'+
                '<a class="btn btn-default btn-block margin-top-10" title="檔案 I10.png 點此另開新視窗" target="_blank" rel="noreferrer noopener" href="/Data/typhoon/I10.png?T='+File_Time+'" data-gtmtitle="颱風警報_右上按鈕_下載警報單">'+
                    '下載警報單 <i class="icon-open" aria-hidden="true"></i>'+
                '</a>'+
            '</div>'+
            '<div class="col-sm-6">'+
                '<a class="btn btn-default btn-block margin-top-10" title="點此前往檢視" target="_self" href="/V8/C/W/index.html#f-3" data-gtmtitle="颱風警報_右上按鈕_口語化說明">'+
                    '口語化說明 <i class="fa fa-plus-square" aria-hidden="true"></i>'+
                '</a>'+
            '</div>'+
            '<div class="col-sm-6" id="WPPS_BTN">'+
                '<a class="btn btn-default btn-block margin-top-10" title="點此前往檢視" target="_self" href="/V8/C/P/Typhoon/WPPS.html?T='+File_Time+'" data-gtmtitle="颱風警報_右上按鈕_風雨預報">'+
                    '風雨預報 <i class="fa fa-plus-square" aria-hidden="true"></i>'+
                '</a>'+
            '</div>';
WPPS_BTN['E'] = ''+
            '<div class="col-sm-12">'+
                '<a class="btn btn-default btn-block margin-top-10" title="Click to open file I11.png " target="_blank" rel="noreferrer noopener" href="/Data/typhoon/I11.png?T='+File_Time+'" data-gtmtitle="Typhoon Warning_Top Right Buttons_TextAndGraph">'+
                    'Text and Graph <i class="icon-open" aria-hidden="true"></i>'+
                '</a>'+
            '</div>';

var TY_WARN_Lv = {'ID':'LAND','C':'海上陸上颱風警報','E':'Sea and Land Typhoon Warning'};

var Movement = '根據最新資料顯示，第29號颱風中心目前在鵝鑾鼻東方海面，向北北西移動，其暴風圈已進入臺灣東半部近海，對臺灣陸地將構成威脅。';

var WarningArea = {"LandWarningArea":"臺灣各地區應嚴加戒備，並防強風豪雨。","SeaWarningArea":"臺灣附近各海面及巴士海峽航行作業船隻應嚴加戒備。","RainWarningArea":""};

var WarningText = {"RainWarning":"第29號颱風及其外圍環流影響，今(23)日宜蘭縣山區有局部大豪雨或超大豪雨，臺北市山區、新北市山區、桃園市山區有局部豪雨或大豪雨，新北市地區、桃園市地區、宜蘭縣地區、新竹縣山區、苗栗縣山區、花蓮縣山區有局部大雨或豪雨，基隆、臺北、新竹、苗栗、花蓮地區及臺中、南投山區有局部大雨發生的機率，請注意瞬間大雨，山區請慎防坍方、落石、土石流，低窪地區請慎防積淹水，應避免前往山區及溪流活動。超大豪雨地區：宜蘭縣。大豪雨地區：臺北市、新北市、桃園市。","GaleWarning":"颱風及其外圍環流影響，今(23)日基隆市、新北市、桃園市、新竹市、新竹縣、苗栗縣、臺中市、彰化縣、雲林縣、嘉義縣、臺南市、高雄市、屏東縣、宜蘭縣、臺東縣(含蘭嶼、綠島)、澎湖縣局部地區有平均風9級以上或陣風11級以上發生的機率(橙色燈號)，臺北市、南投縣、嘉義市、花蓮縣、金門縣、連江縣局部地區有平均風6級以上或陣風8級以上發生的機率(黃色燈號)，請注意防範。"};

var LandWarn = ''; var SeaWarn = ''; var HeavyRain = '';

var NoticeText = [
	'今(23)日臺灣附近各海面風浪偏大，有3公尺以上大浪，尤其東半部(含蘭嶼、綠島)沿海及基隆北海岸、恆春半島易有6公尺以上巨浪，東南部沿海及蘭嶼已出現8公尺以上浪高；臺灣各沿海及蘭嶼、綠島、澎湖、馬祖有長浪發生，請避免前往海邊活動。',
	'室外懸掛物、招牌、圍籬及鷹架等應加強固牢，陽台之盆景等應妥善放置。',
	'高溫資訊：颱風環流沉降影響，今、明(23、24)兩天東南部地區有焚風發生的機率，今(23日)晚起東部地區亦有焚風發生的機率，23日、24日花蓮縣、臺東縣為黃色燈號，請注意。',
	'22日0時至23日2時出現較大陣風區域如下：蘭嶼15級，東吉島12級，花蓮、彭佳嶼、澎湖、成功10級。'
];

var NoteText = [
	'下次警報預定發布時間為10月23日05時30分。'
];

var PTA_TYPHOON = 'CHAMPI';

var TED_PTA = {'C':'','E':''};

TED_PTA['C'] = ''+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A1" title="點此展開" aria-expanded="true">預測 6 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A1" class="panel-collapse collapse in" aria-expanded="true" role="document">'+
            '<div class="panel-body">'+
                '<p>北北西 時速 18 公里'+
                    '<br /> 預測 10月23日08時'+
                    '<br /> 中心位置在北緯 22.7 度，東經 123.9 度'+
                    '<br /> 中心氣壓950百帕'+
                    '<br /> 近中心最大風速每秒 40 公尺'+
                    '<br /> 瞬間最大陣風每秒 50 公尺'+
                    '<br /> 七級風暴風半徑 300 公里'+
                    '<br /> 十級風暴風半徑 120 公里'+
                    '<br /> 70%機率半徑 40 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A2" title="點此展開" aria-expanded=" false">預測 6-12 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A2" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>北北西 時速 24 公里'+
                    '<br /> 預測 10月23日14時'+
                    '<br /> 中心位置在北緯 23.8 度，東經 123.2 度'+
                    '<br /> 中心氣壓950百帕'+
                    '<br /> 近中心最大風速每秒 40 公尺'+
                    '<br /> 瞬間最大陣風每秒 50 公尺'+
                    '<br /> 七級風暴風半徑 300 公里'+
                    '<br /> 十級風暴風半徑 120 公里'+
                    '<br /> 70%機率半徑 50 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A3" title="點此展開" aria-expanded=" false">預測 12-18 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A3" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>西北 時速 16 公里'+
                    '<br /> 預測 10月23日20時'+
                    '<br /> 中心位置在北緯 24.5 度，東經 122.6 度'+
                    '<br /> 中心氣壓950百帕'+
                    '<br /> 近中心最大風速每秒 40 公尺'+
                    '<br /> 瞬間最大陣風每秒 50 公尺'+
                    '<br /> 七級風暴風半徑 300 公里'+
                    '<br /> 十級風暴風半徑 120 公里'+
                    '<br /> 70%機率半徑 80 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A4" title="點此展開" aria-expanded=" false">預測 18-24 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A4" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>北北西 時速 8 公里'+
                    '<br /> 預測 10月24日02時'+
                    '<br /> 中心位置在北緯 24.9 度，東經 122.5 度'+
                    '<br /> 中心氣壓960百帕'+
                    '<br /> 近中心最大風速每秒 38 公尺'+
                    '<br /> 瞬間最大陣風每秒 48 公尺'+
                    '<br /> 七級風暴風半徑 300 公里'+
                    '<br /> 十級風暴風半徑 100 公里'+
                    '<br /> 70%機率半徑 90 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A5" title="點此展開" aria-expanded=" false">預測 24-36 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A5" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>北 時速 16 公里'+
                    '<br /> 預測 10月24日14時'+
                    '<br /> 中心位置在北緯 26.6 度，東經 122.8 度'+
                    '<br /> 中心氣壓970百帕'+
                    '<br /> 近中心最大風速每秒 33 公尺'+
                    '<br /> 瞬間最大陣風每秒 43 公尺'+
                    '<br /> 七級風暴風半徑 280 公里'+
                    '<br /> 十級風暴風半徑 100 公里'+
                    '<br /> 70%機率半徑 100 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A6" title="點此展開" aria-expanded=" false">預測 36-48 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A6" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>北北東 時速 21 公里'+
                    '<br /> 預測 10月25日02時'+
                    '<br /> 中心位置在北緯 28.7 度，東經 123.7 度'+
                    '<br /> 中心氣壓980百帕'+
                    '<br /> 近中心最大風速每秒 28 公尺'+
                    '<br /> 瞬間最大陣風每秒 35 公尺'+
                    '<br /> 七級風暴風半徑 250 公里'+
                    '<br /> 70%機率半徑 150 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A7" title="點此展開" aria-expanded=" false">預測 48-72 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A7" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>東北 時速 21 公里'+
                    '<br /> 預測 10月26日02時'+
                    '<br /> 中心位置在北緯 31.5 度，東經 127.9 度'+
                    '<br /> 中心氣壓998百帕'+
                    '<br /> 近中心最大風速每秒 18 公尺'+
                    '<br /> 瞬間最大陣風每秒 25 公尺'+
                    '<br /> 七級風暴風半徑 120 公里'+
                    '<br /> 70%機率半徑 210 公里'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default Move-120h">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A8" title="點此展開" aria-expanded=" false">預測 72-96 小時平均移向移速為</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A8" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>東北東 時速 19 公里'+
                    '<br /> 預測 10月27日02時'+
                    '<br /> 中心位置在北緯 33.0 度，東經 132.5 度'+
                    '<br /> 中心氣壓998百帕'+
                    '<br /> 70%機率半徑 360 公里'+
                    '<br /> 預測 96 小時內變性為溫帶氣旋'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>';

TED_PTA['E'] = ''+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A1" title="Show more details" aria-expanded="true">6 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A1" class="panel-collapse collapse in" aria-expanded="true" role="document">'+
            '<div class="panel-body">'+
                '<p>0000UTC 23 October 2026'+
                    '<br /> Center Position 22.7N 123.9E'+
                    '<br /> Vector to 6 HR Position'+
                    '<br /> NNW 18 km/h'+
                    '<br /> Minimum Pressure 950 hPa'+
                    '<br /> Maximum Wind Speed 40 m/s'+
                    '<br /> Gust 50 m/s'+
                    '<br /> Radius of over 15m/s winds 300km'+
                    '<br /> Radius of over 25m/s winds 120km'+
                    '<br /> Radius of 70% probability circle 40km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A2" title="Show more details" aria-expanded=" false">12 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A2" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>0600UTC 23 October 2026'+
                    '<br /> Center Position 23.8N 123.2E'+
                    '<br /> Vector to 12 HR Position'+
                    '<br /> NNW 24 km/h'+
                    '<br /> Minimum Pressure 950 hPa'+
                    '<br /> Maximum Wind Speed 40 m/s'+
                    '<br /> Gust 50 m/s'+
                    '<br /> Radius of over 15m/s winds 300km'+
                    '<br /> Radius of over 25m/s winds 120km'+
                    '<br /> Radius of 70% probability circle 50km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A3" title="Show more details" aria-expanded=" false">18 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A3" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>1200UTC 23 October 2026'+
                    '<br /> Center Position 24.5N 122.6E'+
                    '<br /> Vector to 18 HR Position'+
                    '<br /> NW 16 km/h'+
                    '<br /> Minimum Pressure 950 hPa'+
                    '<br /> Maximum Wind Speed 40 m/s'+
                    '<br /> Gust 50 m/s'+
                    '<br /> Radius of over 15m/s winds 300km'+
                    '<br /> Radius of over 25m/s winds 120km'+
                    '<br /> Radius of 70% probability circle 80km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A4" title="Show more details" aria-expanded=" false">24 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A4" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>1800UTC 23 October 2026'+
                    '<br /> Center Position 24.9N 122.5E'+
                    '<br /> Vector to 24 HR Position'+
                    '<br /> NNW 8 km/h'+
                    '<br /> Minimum Pressure 960 hPa'+
                    '<br /> Maximum Wind Speed 38 m/s'+
                    '<br /> Gust 48 m/s'+
                    '<br /> Radius of over 15m/s winds 300km'+
                    '<br /> Radius of over 25m/s winds 100km'+
                    '<br /> Radius of 70% probability circle 90km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A5" title="Show more details" aria-expanded=" false">36 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A5" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>0600UTC 24 October 2026'+
                    '<br /> Center Position 26.6N 122.8E'+
                    '<br /> Vector to 36 HR Position'+
                    '<br /> N 16 km/h'+
                    '<br /> Minimum Pressure 970 hPa'+
                    '<br /> Maximum Wind Speed 33 m/s'+
                    '<br /> Gust 43 m/s'+
                    '<br /> Radius of over 15m/s winds 280km'+
                    '<br /> Radius of over 25m/s winds 100km'+
                    '<br /> Radius of 70% probability circle 100km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A6" title="Show more details" aria-expanded=" false">48 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A6" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>1800UTC 24 October 2026'+
                    '<br /> Center Position 28.7N 123.7E'+
                    '<br /> Vector to 48 HR Position'+
                    '<br /> NNE 21 km/h'+
                    '<br /> Minimum Pressure 980 hPa'+
                    '<br /> Maximum Wind Speed 28 m/s'+
                    '<br /> Gust 35 m/s'+
                    '<br /> Radius of over 15m/s winds 250km'+
                    '<br /> Radius of 70% probability circle 150km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A7" title="Show more details" aria-expanded=" false">72 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A7" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>1800UTC 25 October 2026'+
                    '<br /> Center Position 31.5N 127.9E'+
                    '<br /> Vector to 72 HR Position'+
                    '<br /> NE 21 km/h'+
                    '<br /> Minimum Pressure 998 hPa'+
                    '<br /> Maximum Wind Speed 18 m/s'+
                    '<br /> Gust 25 m/s'+
                    '<br /> Radius of over 15m/s winds 120km'+
                    '<br /> Radius of 70% probability circle 210km'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>'+
    '<div class="panel panel-default Move-120h">'+
        '<div class="panel-heading">'+
            '<h4 class="panel-title">'+
                '<a class="accordion-toggle collapsed" data-toggle="collapse" data-parent="#accordion-1" href="#collapse-A8" title="Show more details" aria-expanded=" false">96 hours valid at:</a>'+
            '</h4>'+
        '</div>'+
        '<div id="collapse-A8" class="panel-collapse collapse" aria-expanded=" false" role="document">'+
            '<div class="panel-body">'+
                '<p>1800UTC 26 October 2026'+
                    '<br /> Center Position 33.0N 132.5E'+
                    '<br /> Vector to 96 HR Position'+
                    '<br /> ENE 19 km/h'+
                    '<br /> Minimum Pressure 998 hPa'+
                    '<br /> Radius of 70% probability circle 360km'+
                    '<br /> Becoming extratropical low at 96 hours'+
                '</p>'+
            '</div>'+
        '</div>'+
    '</div>';
