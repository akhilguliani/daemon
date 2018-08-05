cores=10
#for fname in prio_10_0 prio_10_3 prio_10_5 prio_10_7 prio_10_9
for fname in prio_10_7
do
    for i in 85
    do
        echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores >> results/policy_${fname}_${i}_test"
        python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores >> results/policy_${fname}_${i}_test &
        pypid=$!
        echo $pypid
        sleep 400
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
        sleep 5
    done
done
