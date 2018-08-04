for fname in prio_10_0 prio_10_3	prio_10_5 prio_10_7 prio_10_9
do
    for i in 30 50
    do
        echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i >> results/policy_${fname}_${i}"
        python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=8 >> results/policy_${fname}_${i}_8 &
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
