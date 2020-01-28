const fs = require('fs');
const rp = require('request-promise');

if ('AGENT_PORT' in process.env){
    exports.host = "http://localhost:" + process.env['AGENT_PORT'];
} else {
    exports.host = "http://localhost:5001";
}

exports.getTask = async function(){
    const reqUrl = exports.host + '/get_task';
    let task_data = await rp({uri: reqUrl, method: 'POST', json: true});

    if (typeof(task_data['json_metadata']) == 'string'){
        try{
            task_data['json_metadata'] = JSON.parse(task_data['json_metadata']);
        } catch (e){
            if (!(e instanceof SyntaxError)){
                throw e;
            } 
        }
    }

    return task_data;
}

exports.saveResult = async function(result){
    const reqUrl = exports.host + '/save_results';
    const response = await rp({
        uri: reqUrl,
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: result,
        json: true
    });
    return response;
}

exports.addUrl = async function(url, jsonMetadata=null){
    const reqUrl = exports.host + '/add_url';
    const response = await rp({
        uri: reqUrl,
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: {'url': url, 'json_metadata': jsonMetadata},
        json: true
    });
    return response;
}

exports.logError = async function(errorMsg){
    const reqUrl = exports.host + '/log_error';
    const response = await rp({
        uri: reqUrl,
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: {'message': errorMsg},
        json: true
    })
    return response;
}

exports.saveScreenshot = async function(screenshotPath){
    const reqUrl = exports.host + '/save_screenshot';
    const response = await rp({
        uri: reqUrl,
        method: 'POST',
        formData: {
            screenshot: fs.createReadStream(screenshotPath)
        },
        json: true
    });

    return response;
}